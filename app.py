from flask import Flask, render_template, jsonify, request
import json
import os
import yfinance as yf
from datetime import datetime, timedelta

app = Flask(__name__)

# Load events data
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
with open(os.path.join(DATA_DIR, 'events.json'), encoding='utf-8') as f:
    EVENTS_DATA = json.load(f)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/events')
def get_events():
    """全イベント一覧を返す"""
    return jsonify(EVENTS_DATA)


@app.route('/api/events/search')
def search_events():
    """キーワードやカテゴリでイベントを検索"""
    query = request.args.get('q', '').lower()
    category = request.args.get('category', '')

    results = []
    for event in EVENTS_DATA['events']:
        # カテゴリフィルタ
        if category and event['category'] != category:
            continue
        # キーワード検索（名前、説明、タグ）
        if query:
            searchable = (
                event['name'].lower() +
                event.get('name_en', '').lower() +
                event['description'].lower() +
                ' '.join(event.get('tags', []))
            )
            if query not in searchable:
                continue
        results.append(event)

    return jsonify(results)


@app.route('/api/events/similar/<int:event_id>')
def get_similar_events(event_id):
    """指定イベントと類似のイベントを返す（同カテゴリ + タグ一致）"""
    target = None
    for event in EVENTS_DATA['events']:
        if event['id'] == event_id:
            target = event
            break

    if not target:
        return jsonify({'error': 'Event not found'}), 404

    target_tags = set(target.get('tags', []))
    target_category = target['category']

    scored = []
    for event in EVENTS_DATA['events']:
        if event['id'] == event_id:
            continue
        score = 0
        # 同カテゴリで+3
        if event['category'] == target_category:
            score += 3
        # タグ一致で各+1
        event_tags = set(event.get('tags', []))
        score += len(target_tags & event_tags)

        if score > 0:
            scored.append({'event': event, 'score': score})

    scored.sort(key=lambda x: x['score'], reverse=True)
    return jsonify([item['event'] for item in scored[:10]])


@app.route('/api/stock/<path:symbol>')
def get_stock_data(symbol):
    """株価データを取得（yfinance使用）"""
    start = request.args.get('start')
    end = request.args.get('end')
    margin_days = int(request.args.get('margin', 30))

    if not start or not end:
        return jsonify({'error': 'start and end parameters required'}), 400

    try:
        # 前後にマージンを追加して取得
        start_dt = datetime.strptime(start, '%Y-%m-%d') - timedelta(days=margin_days)
        end_dt = datetime.strptime(end, '%Y-%m-%d') + timedelta(days=margin_days)

        ticker = yf.Ticker(symbol)
        hist = ticker.history(start=start_dt.strftime('%Y-%m-%d'),
                              end=end_dt.strftime('%Y-%m-%d'))

        if hist.empty:
            return jsonify({'error': 'No data available', 'symbol': symbol}), 404

        data = []
        for date, row in hist.iterrows():
            data.append({
                'date': date.strftime('%Y-%m-%d'),
                'open': round(row['Open'], 2),
                'high': round(row['High'], 2),
                'low': round(row['Low'], 2),
                'close': round(row['Close'], 2),
                'volume': int(row['Volume'])
            })

        return jsonify({
            'symbol': symbol,
            'data': data
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/stock/compare')
def compare_stocks():
    """複数イベント期間の株価を正規化して比較"""
    event_ids = request.args.getlist('event_ids')
    symbol = request.args.get('symbol', '^GSPC')
    margin = int(request.args.get('margin', 30))

    results = []
    for eid in event_ids:
        event = None
        for e in EVENTS_DATA['events']:
            if str(e['id']) == str(eid):
                event = e
                break
        if not event:
            continue

        try:
            start_dt = datetime.strptime(event['start_date'], '%Y-%m-%d') - timedelta(days=margin)
            end_dt = datetime.strptime(event['end_date'], '%Y-%m-%d') + timedelta(days=margin)

            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=start_dt.strftime('%Y-%m-%d'),
                                  end=end_dt.strftime('%Y-%m-%d'))

            if hist.empty:
                continue

            # イベント開始日に最も近い日の終値を基準に正規化
            event_start = datetime.strptime(event['start_date'], '%Y-%m-%d')
            base_price = None
            for date, row in hist.iterrows():
                if date.tz_localize(None) >= event_start or base_price is None:
                    base_price = row['Close']
                    break
            if base_price is None or base_price == 0:
                base_price = hist.iloc[0]['Close']

            data = []
            event_start_ts = event_start.timestamp()
            for date, row in hist.iterrows():
                days_from_event = (date.tz_localize(None) - event_start).days
                data.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'days_from_event': days_from_event,
                    'close': round(row['Close'], 2),
                    'normalized': round((row['Close'] / base_price - 1) * 100, 2)
                })

            results.append({
                'event': event,
                'symbol': symbol,
                'data': data
            })

        except Exception:
            continue

    return jsonify(results)


if __name__ == '__main__':
    app.run(debug=True, port=5050)
