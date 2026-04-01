from flask import Flask, render_template, jsonify, request
import json
import os
import yfinance as yf
from datetime import datetime, timedelta
import numpy as np
import feedparser
import threading
import time
import re

app = Flask(__name__)

# ============================================================
# NEWS MONITORING (ニュース監視)
# ============================================================
NEWS_FEEDS = [
    # --- US Major ---
    {'url': 'https://feeds.reuters.com/reuters/businessNews', 'source': 'Reuters Business'},
    {'url': 'https://feeds.reuters.com/reuters/topNews', 'source': 'Reuters'},
    {'url': 'https://feeds.reuters.com/reuters/JPBusinessNews', 'source': 'Reuters Japan'},
    {'url': 'https://www.cnbc.com/id/10001147/device/rss/rss.html', 'source': 'CNBC Markets'},
    {'url': 'https://feeds.marketwatch.com/marketwatch/topstories/', 'source': 'MarketWatch'},
    {'url': 'https://www.investing.com/rss/news_25.rss', 'source': 'Investing.com'},
    {'url': 'https://finance.yahoo.com/rss/topstories', 'source': 'Yahoo Finance'},
    {'url': 'https://www.forexlive.com/feed/news', 'source': 'ForexLive'},
    {'url': 'https://feeds.bloomberg.com/markets/news.rss', 'source': 'Bloomberg Markets'},
    {'url': 'https://feeds.a.dj.com/rss/RSSMarketsMain.xml', 'source': 'WSJ Markets'},
    {'url': 'https://www.ft.com/rss/home', 'source': 'Financial Times'},
    {'url': 'https://feeds.a.dj.com/rss/RSSBarrons.xml', 'source': "Barron's"},
    {'url': 'https://seekingalpha.com/market_currents.xml', 'source': 'Seeking Alpha'},
    {'url': 'https://feeds.feedburner.com/zerohedge/feed', 'source': 'ZeroHedge'},
    # --- Europe ---
    {'url': 'https://www.ecb.europa.eu/rss/press.html', 'source': 'ECB News'},
    {'url': 'http://feeds.bbci.co.uk/news/business/rss.xml', 'source': 'BBC Business'},
    {'url': 'https://www.theguardian.com/uk/business/rss', 'source': 'The Guardian Business'},
    # --- Asia / Japan ---
    {'url': 'https://assets.wor.jp/rss/rdf/nikkei/news.rdf', 'source': 'Nikkei'},
    {'url': 'https://www3.nhk.or.jp/rss/news/cat5.xml', 'source': 'NHK Business'},
    {'url': 'https://www.scmp.com/rss/91/feed', 'source': 'South China Morning Post'},
    {'url': 'https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=6511', 'source': 'Channel News Asia Business'},
    # --- Central Banks ---
    {'url': 'https://www.federalreserve.gov/feeds/press_all.xml', 'source': 'Federal Reserve'},
    {'url': 'https://www.boj.or.jp/rss/whatsnew.xml', 'source': 'Bank of Japan'},
]

MARKET_KEYWORDS = [
    # English
    'fed', 'federal reserve', 'interest rate', 'inflation', 'gdp', 'earnings',
    'stock', 'market', 'nasdaq', 's&p', 'dow', 'economy', 'tariff', 'trade',
    'recession', 'jobs', 'unemployment', 'treasury', 'bond', 'yield', 'oil',
    'dollar', 'central bank', 'rate hike', 'rate cut', 'monetary', 'cpi', 'ppi',
    'fomc', 'ecb', 'boe', 'bank of japan', 'geopolitical', 'sanctions', 'debt', 'yen',
    'euro', 'eurozone', 'lagarde', 'powell', 'semiconductor', 'crude oil',
    'commodity', 'forex', 'nonfarm', 'housing', 'consumer confidence',
    # Japanese
    '金利', '株式', '市場', 'インフレ', '為替', '経済', '日銀', '利上げ', '利下げ',
    '景気', '雇用', '物価', '円安', '円高', '株価', 'GDP',
    'デフレ', '景気後退', 'リセッション', '量的緩和', 'テーパリング',
    '関税', '制裁', '戦争', '停戦', '原油', '半導体',
    # Chinese
    '股市', '央行', '降息',
]

POSITIVE_KEYWORDS = [
    # English
    'surge', 'rally', 'gains', 'record high', 'beats', 'exceeds', 'strong growth',
    'bullish', 'recovery', 'boost', 'rises', 'jumps', 'soars', 'optimism',
    'rate cut', 'stimulus', 'dovish', 'outperform', 'upgrade', 'expansion',
    'profits rise', 'hiring', 'above expectations', 'bailout', 'easing',
    'buyback', 'dividend', 'beat expectations', 'profit surge',
    # Japanese
    '上昇', '回復', '好調', '利下げ', '堅調', '量的緩和', '追加緩和', '景気回復',
]

NEGATIVE_KEYWORDS = [
    # English
    'crash', 'plunge', 'tumble', 'falls', 'declines', 'recession', 'slowdown',
    'misses', 'below expectations', 'concern', 'warning', 'rate hike', 'hawkish',
    'sell-off', 'fear', 'uncertainty', 'tariff', 'sanctions', 'war', 'crisis',
    'default', 'downgrade', 'layoffs', 'contraction', 'stagflation',
    'bankruptcy', 'missile', 'invasion', 'tightening', 'miss expectations',
    # Japanese
    '下落', '低下', '懸念', '利上げ', '悪化', '急落', 'リセッション',
    '戦争', '侵攻', '破綻', 'デフォルト', '景気後退',
]

_news_cache = {'articles': [], 'impact': {'score': 0, 'direction': 'neutral', 'price_impact_pct': 0, 'article_count': 0}, 'timestamp': 0}
NEWS_CACHE_TTL = 900  # 15 minutes


def _calculate_news_impact(articles):
    """Weighted sentiment → short-term price impact estimate"""
    if not articles:
        return {'score': 0, 'direction': 'neutral', 'price_impact_pct': 0, 'article_count': 0}
    now = datetime.now()
    total_score, total_weight = 0.0, 0.0
    for a in articles[:25]:
        try:
            pub = datetime.fromisoformat(a['published'])
            hours_ago = max(0.1, (now - pub).total_seconds() / 3600)
            weight = np.exp(-hours_ago / 12) * max(1, a['relevance'])  # 12h half-life
            total_score += a['sentiment_score'] * weight
            total_weight += weight
        except Exception:
            pass
    avg = total_score / total_weight if total_weight > 0 else 0
    direction = 'bullish' if avg > 0.3 else ('bearish' if avg < -0.3 else 'neutral')
    price_impact = float(np.clip(avg * 0.7, -2.5, 2.5))
    return {
        'score': round(avg, 2),
        'direction': direction,
        'price_impact_pct': round(price_impact, 2),
        'article_count': len(articles),
    }


def fetch_market_news(force=False):
    """Fetch RSS feeds from major financial news sites, cache for 15 min"""
    now = time.time()
    if not force and now - _news_cache['timestamp'] < NEWS_CACHE_TTL and _news_cache['articles']:
        return _news_cache

    all_articles = []
    cutoff = datetime.now() - timedelta(hours=48)

    for feed_config in NEWS_FEEDS:
        try:
            feed = feedparser.parse(feed_config['url'])
            for entry in feed.entries[:15]:
                try:
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_date = datetime(*entry.published_parsed[:6])
                    else:
                        pub_date = datetime.now()
                except Exception:
                    pub_date = datetime.now()

                if pub_date < cutoff:
                    continue

                title = entry.get('title', '')
                summary = entry.get('summary', entry.get('description', ''))
                content = (title + ' ' + summary).lower()

                relevance = sum(1 for kw in MARKET_KEYWORDS if kw in content)
                if relevance == 0:
                    continue

                # Negation-aware sentiment scoring
                sentences = re.split(r'[.!?。！？;；]', content)
                pos = 0
                neg = 0
                negation_words = ['not', 'no', 'never', 'neither', 'nor', 'barely',
                                  'hardly', 'fail', 'fails', 'failed', 'without',
                                  'unlikely', 'ない', 'ず', 'ません']
                for sent in sentences:
                    sent_lower = sent.lower().strip()
                    if not sent_lower:
                        continue
                    has_negation = any(nw in sent_lower for nw in negation_words)
                    sent_pos = sum(1 for kw in POSITIVE_KEYWORDS if kw in sent_lower)
                    sent_neg = sum(1 for kw in NEGATIVE_KEYWORDS if kw in sent_lower)
                    if has_negation:
                        # Flip sentiment when negation detected
                        pos += sent_neg
                        neg += sent_pos
                    else:
                        pos += sent_pos
                        neg += sent_neg

                if pos > neg:
                    sentiment = 'bullish'
                    s_score = pos - neg
                elif neg > pos:
                    sentiment = 'bearish'
                    s_score = -(neg - pos)
                else:
                    sentiment = 'neutral'
                    s_score = 0

                all_articles.append({
                    'title': title,
                    'url': entry.get('link', '#'),
                    'source': feed_config['source'],
                    'published': pub_date.isoformat(),
                    'published_str': pub_date.strftime('%m/%d %H:%M'),
                    'sentiment': sentiment,
                    'sentiment_score': s_score,
                    'relevance': relevance,
                })
        except Exception as e:
            print(f"Feed error [{feed_config['source']}]: {e}")

    # Sort by recency, deduplicate by title
    all_articles.sort(key=lambda x: x['published'], reverse=True)
    seen = set()
    unique = []
    for a in all_articles:
        key = a['title'][:45].lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(a)
    unique = unique[:35]

    impact = _calculate_news_impact(unique)
    _news_cache['articles'] = unique
    _news_cache['impact'] = impact
    _news_cache['timestamp'] = now
    print(f"[News] Fetched {len(unique)} articles, impact={impact['direction']} ({impact['price_impact_pct']:+.2f}%)")
    return _news_cache


def _news_refresh_loop():
    """Background thread: refresh news every 15 minutes"""
    time.sleep(10)  # Wait for app startup
    while True:
        try:
            fetch_market_news(force=True)
        except Exception as e:
            print(f"[News BG] Error: {e}")
        time.sleep(NEWS_CACHE_TTL)


_news_bg_thread = threading.Thread(target=_news_refresh_loop, daemon=True)
_news_bg_thread.start()

def estimate_garch11(returns, omega_init=0.00001, alpha_init=0.1, beta_init=0.85, n_iter=50):
    """Simple GARCH(1,1) estimation via variance targeting + grid search.
    sigma2(t) = omega + alpha * r(t-1)^2 + beta * sigma2(t-1)
    Returns (omega, alpha, beta, conditional_variances)
    """
    T = len(returns)
    if T < 30:
        var = float(np.var(returns))
        return var * 0.05, 0.1, 0.85, np.full(T, var)

    # Variance targeting: omega = long_run_var * (1 - alpha - beta)
    long_run_var = float(np.var(returns))

    best_ll = -np.inf
    best_params = (omega_init, alpha_init, beta_init)
    best_sigma2 = None

    # Grid search over alpha and beta
    for alpha in [0.04, 0.06, 0.08, 0.10, 0.12, 0.15]:
        for beta in [0.80, 0.82, 0.84, 0.86, 0.88, 0.90, 0.92]:
            if alpha + beta >= 0.999:
                continue
            omega = long_run_var * (1 - alpha - beta)
            if omega <= 0:
                continue

            sigma2 = np.zeros(T)
            sigma2[0] = long_run_var

            for t in range(1, T):
                sigma2[t] = omega + alpha * returns[t-1]**2 + beta * sigma2[t-1]
                if sigma2[t] <= 0:
                    sigma2[t] = long_run_var

            # Log-likelihood (Gaussian)
            ll = -0.5 * np.sum(np.log(sigma2 + 1e-12) + returns**2 / (sigma2 + 1e-12))
            if ll > best_ll:
                best_ll = ll
                best_params = (omega, alpha, beta)
                best_sigma2 = sigma2.copy()

    if best_sigma2 is None:
        best_sigma2 = np.full(T, long_run_var)

    return best_params[0], best_params[1], best_params[2], best_sigma2


def fetch_fred_indicators():
    """Fetch key macro indicators from FRED API (optional, requires FRED_API_KEY env var)"""
    api_key = os.environ.get('FRED_API_KEY', '')
    if not api_key:
        return None

    import requests as req
    indicators = {}
    series_map = {
        'cpi_yoy': 'CPIAUCSL',           # CPI
        'unemployment': 'UNRATE',          # Unemployment rate
        'fed_funds': 'FEDFUNDS',           # Fed funds rate
        'consumer_sentiment': 'UMCSENT',   # U of Michigan consumer sentiment
        'pmi_manufacturing': 'MANEMP',     # Manufacturing employment (proxy)
        'initial_claims': 'ICSA',          # Initial jobless claims
        'retail_sales': 'RSXFS',           # Retail sales ex food services
        'housing_starts': 'HOUST',         # Housing starts
    }

    for key, series_id in series_map.items():
        try:
            url = f'https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={api_key}&file_type=json&sort_order=desc&limit=2'
            r = req.get(url, timeout=10)
            if r.status_code == 200:
                obs = r.json().get('observations', [])
                if len(obs) >= 2:
                    current = float(obs[0]['value']) if obs[0]['value'] != '.' else None
                    previous = float(obs[1]['value']) if obs[1]['value'] != '.' else None
                    if current is not None and previous is not None:
                        change = current - previous
                        change_pct = (change / abs(previous) * 100) if previous != 0 else 0
                        indicators[key] = {
                            'value': round(current, 2),
                            'previous': round(previous, 2),
                            'change': round(change, 2),
                            'change_pct': round(change_pct, 2),
                            'date': obs[0]['date'],
                        }
        except Exception as e:
            print(f"FRED error [{series_id}]: {e}")

    return indicators if indicators else None


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

        # Yahoo Financeは1950年以前のデータがないためスキップ
        if start_dt.year < 1950:
            return jsonify({'error': 'No data available before 1950', 'symbol': symbol}), 404

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

            # 1950年以前はYahoo Financeにデータなし
            if start_dt.year < 1950:
                continue

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


@app.route('/api/predict/<path:symbol>')
def predict_stock(symbol):
    """多因子経済モデルによる株価予測エンジン

    Components:
    1. Market Regime Detection (マルコフ・レジーム)
    2. Mean Reversion (Ornstein-Uhlenbeck, 平均回帰)
    3. Momentum (RSI, MACD, ROC)
    4. Volatility Model (EWMA)
    5. Cross-Asset Signal Analysis (クロスアセット)
    6. Historical Pattern Matching (改良版)
    7. Composite Forecast (ベイズ合成)
    8. Monte Carlo Confidence Bands
    9. Risk Metrics
    """
    from collections import OrderedDict
    import math

    forecast_days = int(request.args.get('forecast_days', 90))
    lookback_days = int(request.args.get('lookback_days', 365))

    try:
        # ============================================================
        # DATA ACQUISITION - 株価・クロスアセットデータ取得
        # ============================================================
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=lookback_days)
        ticker = yf.Ticker(symbol)
        current_hist = ticker.history(start=start_dt.strftime('%Y-%m-%d'),
                                       end=end_dt.strftime('%Y-%m-%d'))
        if current_hist.empty:
            return jsonify({'error': 'No current data available'}), 404

        closes = np.array(current_hist['Close'].values, dtype=float)
        highs = np.array(current_hist['High'].values, dtype=float)
        lows = np.array(current_hist['Low'].values, dtype=float)
        volumes = np.array(current_hist['Volume'].values, dtype=float)
        n = len(closes)

        current_data = []
        for date, row in current_hist.iterrows():
            current_data.append({
                'date': date.strftime('%Y-%m-%d'),
                'close': round(float(row['Close']), 2)
            })

        last_price = float(closes[-1])
        last_date = current_data[-1]['date']

        # Daily log returns
        log_returns = np.diff(np.log(closes))

        # ============================================================
        # 1. MARKET REGIME DETECTION (マルコフ・レジーム)
        # ============================================================
        def calc_sma(data, window):
            """Simple moving average"""
            if len(data) < window:
                return np.full(len(data), np.mean(data))
            sma = np.convolve(data, np.ones(window) / window, mode='valid')
            pad = np.full(window - 1, sma[0])
            return np.concatenate([pad, sma])

        sma_50 = calc_sma(closes, min(50, n))
        sma_200 = calc_sma(closes, min(200, n))

        # Golden Cross / Death Cross detection
        ma_cross_signal = float(sma_50[-1] - sma_200[-1]) / sma_200[-1] * 100 if sma_200[-1] != 0 else 0

        # Bollinger Bands (20-day, 2 std)
        bb_window = min(20, n)
        bb_sma = calc_sma(closes, bb_window)
        bb_rolling_std = np.array([
            np.std(closes[max(0, i - bb_window + 1):i + 1]) for i in range(n)
        ])
        bb_upper = bb_sma + 2 * bb_rolling_std
        bb_lower = bb_sma - 2 * bb_rolling_std
        bb_width = float((bb_upper[-1] - bb_lower[-1]) / bb_sma[-1] * 100) if bb_sma[-1] != 0 else 5.0
        bb_percentile = float((closes[-1] - bb_lower[-1]) / (bb_upper[-1] - bb_lower[-1])) if (bb_upper[-1] - bb_lower[-1]) != 0 else 0.5

        # Market regime classification with hysteresis
        if ma_cross_signal > 1.5 and bb_width < 12:
            regime = 'bull'
        elif ma_cross_signal < -1.5 or (ma_cross_signal < 0 and bb_width > 15):
            regime = 'bear'
        elif bb_width > 12:
            regime = 'high_volatility'
        else:
            regime = 'sideways'

        # Hysteresis: require stronger signal to change regime
        # (Compare current RSI and momentum to avoid regime flip-flopping)
        # Note: rsi_14 and momentum_score are computed later; use raw indicators here
        # We use ma_cross_signal and bb_width as proxies for now
        if regime == 'sideways':
            # Use raw momentum proxy from ROC
            _roc_proxy = float((closes[-1] / closes[-min(20, n):][0] - 1) * 100) if n > 1 else 0
            if ma_cross_signal > 0.5 and _roc_proxy > 0:
                regime = 'bull'
            elif ma_cross_signal < -0.5 and _roc_proxy < 0:
                regime = 'bear'

        regime_labels = {
            'bull': 'Bull (強気相場)',
            'bear': 'Bear (弱気相場)',
            'high_volatility': 'High Volatility (高ボラティリティ)',
            'sideways': 'Sideways (レンジ相場)',
        }
        regime_label = regime_labels.get(regime, 'Sideways (レンジ相場)')

        # Regime weight multipliers for historical patterns
        regime_weights = {
            'bull': {'financial_crisis': 0.6, 'trade_war': 0.8, 'pandemic': 0.7, 'war': 0.7, 'oil_crisis': 0.8, 'political': 1.0, 'terrorism': 0.7, 'natural_disaster': 0.7},
            'bear': {'financial_crisis': 1.5, 'trade_war': 1.3, 'pandemic': 1.4, 'war': 1.2, 'oil_crisis': 1.3, 'political': 1.0, 'terrorism': 1.1, 'natural_disaster': 1.0},
            'high_volatility': {'financial_crisis': 1.4, 'trade_war': 1.2, 'pandemic': 1.3, 'war': 1.1, 'oil_crisis': 1.2, 'political': 0.9, 'terrorism': 1.0, 'natural_disaster': 0.9},
            'sideways': {'financial_crisis': 0.8, 'trade_war': 1.0, 'pandemic': 0.9, 'war': 0.9, 'oil_crisis': 1.0, 'political': 1.1, 'terrorism': 0.9, 'natural_disaster': 0.8},
        }

        # ============================================================
        # 2. MEAN REVERSION (Ornstein-Uhlenbeck, 平均回帰)
        # ============================================================
        # Estimate OU parameters: dX = θ(μ - X)dt + σdW
        # Use OLS regression: X(t+1) - X(t) = a + b*X(t) + ε
        # θ = -b, μ = -a/b, σ = std(ε) * sqrt(2θ)
        if n > 30:
            X = np.log(closes)
            dX = np.diff(X)
            X_lag = X[:-1]
            # OLS: dX = a + b * X_lag
            A = np.column_stack([np.ones(len(X_lag)), X_lag])
            try:
                params = np.linalg.lstsq(A, dX, rcond=None)[0]
                a_ou, b_ou = params
                if b_ou < 0:
                    theta = -b_ou * 252  # annualize
                    mu_ou = -a_ou / b_ou  # long-term mean (log price)
                    residuals = dX - (a_ou + b_ou * X_lag)
                    sigma_ou = float(np.std(residuals)) * np.sqrt(252)
                    half_life = np.log(2) / theta if theta > 0 else 999
                else:
                    # No mean reversion detected, use weak pull
                    theta = 0.1
                    mu_ou = float(np.mean(X))
                    sigma_ou = float(np.std(dX)) * np.sqrt(252)
                    half_life = np.log(2) / theta
            except Exception:
                theta = 0.1
                mu_ou = float(np.mean(np.log(closes)))
                sigma_ou = float(np.std(log_returns)) * np.sqrt(252)
                half_life = np.log(2) / theta
        else:
            theta = 0.1
            mu_ou = float(np.mean(np.log(closes)))
            sigma_ou = float(np.std(log_returns)) * np.sqrt(252) if len(log_returns) > 1 else 0.2
            half_life = np.log(2) / theta

        # Mean reversion forecast: E[X(t)] = μ + (X(0) - μ) * exp(-θt)
        current_log_price = np.log(last_price)
        mr_forecasts = {}
        for day in range(0, forecast_days + 1):
            t = day / 252.0
            expected_log = mu_ou + (current_log_price - mu_ou) * np.exp(-theta * t)
            mr_forecasts[day] = (np.exp(expected_log) / last_price - 1) * 100

        # ============================================================
        # 3. MOMENTUM FACTOR (モメンタム)
        # ============================================================
        # RSI (14-day) — Wilder's smoothed RSI
        rsi_period = 14
        closes_arr = closes
        if len(closes_arr) < rsi_period + 1:
            rsi_14 = 50.0
        else:
            deltas = np.diff(closes_arr)
            gains_arr = np.where(deltas > 0, deltas, 0.0)
            losses_arr = np.where(deltas < 0, -deltas, 0.0)
            # Wilder's EMA (equivalent to EMA with alpha = 1/period)
            avg_gain = np.mean(gains_arr[:rsi_period])
            avg_loss = np.mean(losses_arr[:rsi_period])
            for i in range(rsi_period, len(gains_arr)):
                avg_gain = (avg_gain * (rsi_period - 1) + gains_arr[i]) / rsi_period
                avg_loss = (avg_loss * (rsi_period - 1) + losses_arr[i]) / rsi_period
            if avg_loss == 0:
                rsi_14 = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi_14 = 100.0 - (100.0 / (1.0 + rs))

        # MACD (12, 26, 9)
        def calc_ema(data, span):
            alpha = 2 / (span + 1)
            ema = np.zeros(len(data))
            ema[0] = data[0]
            for i in range(1, len(data)):
                ema[i] = alpha * data[i] + (1 - alpha) * ema[i - 1]
            return ema

        ema_12 = calc_ema(closes, 12)
        ema_26 = calc_ema(closes, 26)
        macd_line = ema_12 - ema_26
        macd_signal = calc_ema(macd_line, 9)
        macd_histogram = float(macd_line[-1] - macd_signal[-1])
        macd_normalized = macd_histogram / last_price * 100 if last_price != 0 else 0

        # Rate of Change at multiple timeframes
        def calc_roc(prices, period):
            if len(prices) <= period:
                return 0.0
            return float((prices[-1] / prices[-period - 1] - 1) * 100)

        roc_5 = calc_roc(closes, 5)
        roc_10 = calc_roc(closes, 10)
        roc_20 = calc_roc(closes, 20)
        roc_60 = calc_roc(closes, min(60, n - 1))

        # Composite momentum score (-100 to +100)
        rsi_signal = (rsi_14 - 50) * 2  # -100 to +100
        macd_signal_score = np.clip(macd_normalized * 20, -100, 100)
        roc_composite = np.clip((roc_5 * 4 + roc_10 * 3 + roc_20 * 2 + roc_60 * 1) / 10 * 10, -100, 100)
        momentum_score = float(rsi_signal * 0.3 + macd_signal_score * 0.4 + roc_composite * 0.3)

        # Hysteresis: refine regime using RSI and momentum (now that they're computed)
        if regime == 'sideways':
            if rsi_14 > 60 and momentum_score > 0:
                regime = 'bull'
                regime_label = regime_labels.get('bull', 'Bull (強気相場)')
            elif rsi_14 < 40 and momentum_score < 0:
                regime = 'bear'
                regime_label = regime_labels.get('bear', 'Bear (弱気相場)')

        # Momentum daily forecast (annualized)
        momentum_annual_pct = np.clip(momentum_score * 0.3, -50, 50)
        momentum_forecasts = {}
        for day in range(0, forecast_days + 1):
            # Scale by day proportion, but use longer decay (half-life = 60 days)
            decay = np.exp(-day / 60.0)
            momentum_forecasts[day] = momentum_annual_pct * (day / 252.0) * decay

        # ============================================================
        # 4. VOLATILITY MODEL (EWMA ボラティリティ)
        # ============================================================
        # EWMA volatility with lambda = 0.94 (RiskMetrics)
        ewma_lambda = 0.94
        ewma_var = np.zeros(len(log_returns))
        ewma_var[0] = log_returns[0] ** 2
        for i in range(1, len(log_returns)):
            ewma_var[i] = ewma_lambda * ewma_var[i - 1] + (1 - ewma_lambda) * log_returns[i] ** 2
        ewma_vol_daily = float(np.sqrt(ewma_var[-1])) if len(ewma_var) > 0 else 0.01
        ewma_vol_annual = ewma_vol_daily * np.sqrt(252) * 100

        # Volatility term structure: short (10d) vs long (60d)
        short_vol = float(np.std(log_returns[-min(10, len(log_returns)):]) * np.sqrt(252) * 100) if len(log_returns) > 2 else 20.0
        long_vol = float(np.std(log_returns[-min(60, len(log_returns)):]) * np.sqrt(252) * 100) if len(log_returns) > 2 else 20.0
        vol_term_structure = short_vol - long_vol  # positive = backwardation (stressed)

        current_volatility = round(ewma_vol_annual, 1)

        # ============================================================
        # 5. CROSS-ASSET SIGNAL ANALYSIS (クロスアセット)
        # ============================================================
        factors = {}
        cross_asset_signals = {}
        factor_symbols = {
            'vix': '^VIX',
            'gold': 'GC=F',
            'oil': 'CL=F',
            'usdjpy': 'JPY=X',
            'us10y': '^TNX',
            'dxy': 'DX-Y.NYB',
            'us2y': '^IRX',      # 2-year proxy (13-week T-bill)
            'hyg': 'HYG',        # High yield bond ETF
            'lqd': 'LQD',        # Investment grade bond ETF
            'spy': 'SPY',        # S&P 500 ETF
        }

        cross_asset_data = {}
        for fname, fsym in factor_symbols.items():
            try:
                ft = yf.Ticker(fsym)
                fh = ft.history(period='6mo')
                if not fh.empty:
                    fa = np.array(fh['Close'].values, dtype=float)
                    current_val = round(float(fa[-1]), 2)
                    prev_val = round(float(fa[0]), 2) if len(fa) > 1 else current_val
                    change = round((current_val / prev_val - 1) * 100, 2) if prev_val != 0 else 0
                    factors[fname] = {
                        'value': current_val,
                        'change': change
                    }
                    cross_asset_data[fname] = fa
            except Exception:
                pass

        # Calculate z-scores for cross-asset signals
        def z_score_percentile(data):
            """Return z-score of current value vs history"""
            if len(data) < 10:
                return 0.0, 50.0
            mu = np.mean(data)
            sigma = np.std(data)
            if sigma == 0:
                return 0.0, 50.0
            z = float((data[-1] - mu) / sigma)
            # Approximate percentile from z-score
            pct = float(0.5 * (1 + math.erf(z / math.sqrt(2)))) * 100
            return z, pct

        composite_cross_asset_score = 0.0
        cross_signal_count = 0

        # VIX → risk regime (high VIX = bearish signal)
        if 'vix' in cross_asset_data:
            vix_z, vix_pct = z_score_percentile(cross_asset_data['vix'])
            cross_asset_signals['vix'] = {
                'z_score': round(vix_z, 2),
                'percentile': round(vix_pct, 1),
                'signal': 'risk_off' if vix_pct > 70 else ('risk_on' if vix_pct < 30 else 'neutral'),
                'contribution': round(-vix_z * 3, 2)  # high VIX = negative for stocks
            }
            composite_cross_asset_score += -vix_z * 3
            cross_signal_count += 1

        # Gold/SPY ratio → risk appetite (rising = risk off)
        if 'gold' in cross_asset_data and 'spy' in cross_asset_data:
            min_len = min(len(cross_asset_data['gold']), len(cross_asset_data['spy']))
            gold_spy = cross_asset_data['gold'][-min_len:] / cross_asset_data['spy'][-min_len:]
            gs_z, gs_pct = z_score_percentile(gold_spy)
            cross_asset_signals['gold_spy_ratio'] = {
                'z_score': round(gs_z, 2),
                'percentile': round(gs_pct, 1),
                'signal': 'risk_off' if gs_pct > 70 else ('risk_on' if gs_pct < 30 else 'neutral'),
                'contribution': round(-gs_z * 2, 2)
            }
            composite_cross_asset_score += -gs_z * 2
            cross_signal_count += 1

        # Oil trend → inflation pressure
        if 'oil' in cross_asset_data:
            oil_z, oil_pct = z_score_percentile(cross_asset_data['oil'])
            cross_asset_signals['oil'] = {
                'z_score': round(oil_z, 2),
                'percentile': round(oil_pct, 1),
                'signal': 'inflation_pressure' if oil_pct > 70 else ('deflation' if oil_pct < 30 else 'neutral'),
                'contribution': round(-oil_z * 1.5, 2)
            }
            composite_cross_asset_score += -oil_z * 1.5
            cross_signal_count += 1

        # DXY (USD strength) → liquidity conditions (strong USD = tighter)
        if 'dxy' in cross_asset_data:
            dxy_z, dxy_pct = z_score_percentile(cross_asset_data['dxy'])
            cross_asset_signals['dxy'] = {
                'z_score': round(dxy_z, 2),
                'percentile': round(dxy_pct, 1),
                'signal': 'tight_liquidity' if dxy_pct > 70 else ('loose_liquidity' if dxy_pct < 30 else 'neutral'),
                'contribution': round(-dxy_z * 2, 2)
            }
            composite_cross_asset_score += -dxy_z * 2
            cross_signal_count += 1

        # Yield curve slope (10Y - 2Y proxy) → recession probability
        if 'us10y' in cross_asset_data and 'us2y' in cross_asset_data:
            min_len = min(len(cross_asset_data['us10y']), len(cross_asset_data['us2y']))
            spread = cross_asset_data['us10y'][-min_len:] - cross_asset_data['us2y'][-min_len:]
            sp_z, sp_pct = z_score_percentile(spread)
            is_inverted = float(spread[-1]) < 0
            cross_asset_signals['yield_curve'] = {
                'z_score': round(sp_z, 2),
                'percentile': round(sp_pct, 1),
                'spread': round(float(spread[-1]), 2),
                'inverted': is_inverted,
                'signal': 'recession_warning' if is_inverted else ('expansion' if sp_pct > 60 else 'neutral'),
                'contribution': round(sp_z * 2 + (-3 if is_inverted else 0), 2)
            }
            composite_cross_asset_score += sp_z * 2 + (-3 if is_inverted else 0)
            cross_signal_count += 1

        # Credit spreads (HYG/LQD ratio) → credit stress
        if 'hyg' in cross_asset_data and 'lqd' in cross_asset_data:
            min_len = min(len(cross_asset_data['hyg']), len(cross_asset_data['lqd']))
            credit_ratio = cross_asset_data['hyg'][-min_len:] / cross_asset_data['lqd'][-min_len:]
            cr_z, cr_pct = z_score_percentile(credit_ratio)
            cross_asset_signals['credit_spread'] = {
                'z_score': round(cr_z, 2),
                'percentile': round(cr_pct, 1),
                'signal': 'credit_stress' if cr_pct < 30 else ('healthy' if cr_pct > 60 else 'neutral'),
                'contribution': round(cr_z * 2, 2)  # low ratio (HYG underperforms) = stress
            }
            composite_cross_asset_score += cr_z * 2
            cross_signal_count += 1

        # Normalize composite cross-asset score to annualized % contribution
        if cross_signal_count > 0:
            cross_asset_annual = float(np.clip(composite_cross_asset_score / cross_signal_count * 5, -30, 30))
        else:
            cross_asset_annual = 0.0

        cross_asset_forecasts = {}
        for day in range(0, forecast_days + 1):
            cross_asset_forecasts[day] = cross_asset_annual * (day / 252.0)

        # ============================================================
        # 6. HISTORICAL PATTERN MATCHING (改良版)
        # ============================================================
        # Current price trajectory for correlation matching (last 30 trading days, normalized)
        recent_window = min(30, n)
        recent_normalized = (closes[-recent_window:] / closes[-recent_window] - 1) * 100
        recent_vol = float(np.std(log_returns[-recent_window:])) * np.sqrt(252) if len(log_returns) >= recent_window else 0.2

        event_patterns = []

        # Pre-filter events to reduce API calls (memory optimization for 512MB)
        candidate_events = []
        for event in EVENTS_DATA['events']:
            ev_start = datetime.strptime(event['start_date'], '%Y-%m-%d')
            if ev_start.year < 1950:
                continue
            years_ago = (datetime.now() - ev_start).days / 365.25
            pre_score = max(0.2, np.exp(-years_ago * 0.03))
            cat = event.get('category', '')
            regime_cat_weights = regime_weights.get(regime, {})
            pre_score *= regime_cat_weights.get(cat, 1.0)
            candidate_events.append((pre_score, event))
        candidate_events.sort(key=lambda x: x[0], reverse=True)
        candidate_events = candidate_events[:30]  # Top 30 only

        for _, event in candidate_events:
            try:
                ev_start = datetime.strptime(event['start_date'], '%Y-%m-%d')
                ev_end = datetime.strptime(event['end_date'], '%Y-%m-%d')

                pat_start = ev_start - timedelta(days=45)
                pat_end = ev_end + timedelta(days=forecast_days + 10)

                pat_ticker = yf.Ticker(symbol)
                pat_hist = pat_ticker.history(start=pat_start.strftime('%Y-%m-%d'),
                                               end=pat_end.strftime('%Y-%m-%d'))
                if pat_hist.empty or len(pat_hist) < 10:
                    continue

                pat_closes = np.array(pat_hist['Close'].values, dtype=float)
                pat_log_ret = np.diff(np.log(pat_closes))

                # Find base index (event start)
                base_price = None
                base_idx = 0
                for idx_i, (date, row) in enumerate(pat_hist.iterrows()):
                    if date.tz_localize(None) >= ev_start:
                        base_price = float(row['Close'])
                        base_idx = idx_i
                        break
                if base_price is None or base_price == 0:
                    base_price = float(pat_closes[0])

                # Post-event data
                post_event_data = []
                for idx_i in range(base_idx, len(pat_hist)):
                    date = pat_hist.index[idx_i]
                    days_after = (date.tz_localize(None) - ev_start).days
                    normalized_pct = (float(pat_closes[idx_i]) / base_price - 1) * 100
                    post_event_data.append({
                        'day': days_after,
                        'change_pct': float(normalized_pct)
                    })

                if len(post_event_data) < 5:
                    continue

                # --- Improved Similarity Scoring ---
                score = 1.0

                # (a) Category weight adjusted by regime
                cat = event['category']
                regime_cat_weights = regime_weights.get(regime, {})
                score *= regime_cat_weights.get(cat, 1.0)

                # (b) Recency weight (exponential decay)
                years_ago = (datetime.now() - ev_start).days / 365.25
                recency_weight = max(0.2, np.exp(-years_ago * 0.03))
                score *= recency_weight

                # (c) Volatility regime similarity
                if base_idx > 10:
                    pre_event_returns = pat_log_ret[max(0, base_idx - 30):base_idx]
                    if len(pre_event_returns) > 2:
                        event_vol = float(np.std(pre_event_returns)) * np.sqrt(252)
                        vol_similarity = max(0.3, 1.0 - abs(event_vol - recent_vol) / max(recent_vol, 0.01))
                        score *= vol_similarity

                # (d) Correlation-based matching of recent price action
                if base_idx >= recent_window:
                    pre_event_prices = pat_closes[base_idx - recent_window:base_idx]
                    pre_event_normalized = (pre_event_prices / pre_event_prices[0] - 1) * 100
                    if len(pre_event_normalized) == len(recent_normalized):
                        corr = float(np.corrcoef(recent_normalized, pre_event_normalized)[0, 1])
                        if not np.isnan(corr):
                            corr_weight = max(0.2, (1 + corr) / 2)  # maps [-1,1] to [0,1]
                            score *= corr_weight

                # (e) Separate bull/bear outcome classification
                final_pct = post_event_data[-1]['change_pct'] if post_event_data else 0
                max_dd = min(d['change_pct'] for d in post_event_data)
                outcome = 'bull' if final_pct > 0 else 'bear'

                event_patterns.append({
                    'event_id': event['id'],
                    'event_name': event['name'],
                    'event_name_en': event.get('name_en', ''),
                    'category': cat,
                    'start_date': event['start_date'],
                    'score': round(float(score), 3),
                    'data': post_event_data,
                    'max_drawdown': round(float(max_dd), 2),
                    'final_change': round(float(final_pct), 2),
                    'outcome': outcome
                })

            except Exception:
                continue

        # Sort by score, take top patterns
        event_patterns.sort(key=lambda x: x['score'], reverse=True)
        top_patterns = event_patterns[:15]

        # Build historical pattern forecast
        historical_forecasts = {}
        historical_std = {}
        if top_patterns:
            for day in range(0, forecast_days + 1):
                weighted_sum = 0
                weight_total = 0
                values_at_day = []

                for pat in top_patterns:
                    closest = None
                    min_diff = float('inf')
                    for d in pat['data']:
                        diff = abs(d['day'] - day)
                        if diff < min_diff:
                            min_diff = diff
                            closest = d
                    if closest and min_diff <= 5:
                        weighted_sum += closest['change_pct'] * pat['score']
                        weight_total += pat['score']
                        values_at_day.append(closest['change_pct'])

                if weight_total > 0 and values_at_day:
                    avg = weighted_sum / weight_total
                    std = float(np.std(values_at_day)) if len(values_at_day) > 1 else abs(avg) * 0.3
                    historical_forecasts[day] = avg
                    historical_std[day] = std

        # ============================================================
        # 7. COMPOSITE FORECAST (合成予測 + ベイズ更新)
        # ============================================================
        # Regime-specific model weights
        regime_model_weights = {
            'bull':            {'hist': 0.30, 'mr': 0.10, 'mom': 0.30, 'cross': 0.15, 'regime': 0.15},
            'bear':            {'hist': 0.30, 'mr': 0.30, 'mom': 0.10, 'cross': 0.15, 'regime': 0.15},
            'high_volatility': {'hist': 0.25, 'mr': 0.25, 'mom': 0.10, 'cross': 0.25, 'regime': 0.15},
            'sideways':        {'hist': 0.35, 'mr': 0.25, 'mom': 0.15, 'cross': 0.15, 'regime': 0.10},
        }
        rw = regime_model_weights.get(regime, regime_model_weights['sideways'])
        W_HIST = rw['hist']
        W_MR = rw['mr']
        W_MOM = rw['mom']
        W_CROSS = rw['cross']
        W_REGIME = rw['regime']

        # Regime adjustment: directional bias
        regime_bias_annual = {
            'bull': 8.0,
            'bear': -8.0,
            'high_volatility': -3.0,
            'sideways': 0.0
        }
        regime_annual = regime_bias_annual.get(regime, 0.0)

        regime_forecasts = {}
        for day in range(0, forecast_days + 1):
            regime_forecasts[day] = regime_annual * (day / 252.0)

        # Composite forecast with Bayesian updating
        prediction = []
        all_days = sorted(set(
            list(range(0, forecast_days + 1, 1))
        ))

        for day in all_days:
            if day > forecast_days:
                break

            components = {}
            weights_used = {}

            # Historical component
            if day in historical_forecasts:
                components['historical'] = historical_forecasts[day]
                weights_used['historical'] = W_HIST
            else:
                # Interpolate from nearest
                available_days = sorted(historical_forecasts.keys())
                if available_days:
                    nearest = min(available_days, key=lambda d: abs(d - day))
                    if abs(nearest - day) <= 10:
                        components['historical'] = historical_forecasts[nearest]
                        weights_used['historical'] = W_HIST * 0.7  # reduced confidence

            # Mean reversion component
            if day in mr_forecasts:
                components['mean_reversion'] = mr_forecasts[day]
                weights_used['mean_reversion'] = W_MR

            # Momentum component
            if day in momentum_forecasts:
                components['momentum'] = momentum_forecasts[day]
                weights_used['momentum'] = W_MOM

            # Cross-asset component
            if day in cross_asset_forecasts:
                components['cross_asset'] = cross_asset_forecasts[day]
                weights_used['cross_asset'] = W_CROSS

            # Regime component
            if day in regime_forecasts:
                components['regime'] = regime_forecasts[day]
                weights_used['regime'] = W_REGIME

            if not components:
                continue

            # Normalize weights
            total_weight = sum(weights_used.values())
            if total_weight == 0:
                continue

            # Bayesian composite: weighted average as prior, update with likelihood
            composite_pct = sum(
                components[k] * weights_used[k] / total_weight
                for k in components
            )

            # Bayesian updating: use historical std as likelihood width
            if day in historical_std and historical_std[day] > 0:
                # Prior: composite forecast with uncertainty
                prior_mu = composite_pct
                prior_sigma = ewma_vol_annual * np.sqrt(day / 252.0) if day > 0 else 1.0
                # Likelihood: historical data
                likelihood_mu = historical_forecasts.get(day, composite_pct)
                likelihood_sigma = historical_std.get(day, prior_sigma)

                if prior_sigma > 0 and likelihood_sigma > 0:
                    # Posterior = weighted combination
                    posterior_var = 1.0 / (1.0 / prior_sigma**2 + 1.0 / likelihood_sigma**2)
                    posterior_mu = posterior_var * (prior_mu / prior_sigma**2 + likelihood_mu / likelihood_sigma**2)
                    composite_pct = posterior_mu

            predicted_price = last_price * (1 + composite_pct / 100)

            prediction.append({
                'day': day,
                'change_pct': round(float(composite_pct), 2),
                'price': round(float(predicted_price), 2),
                'components': {k: round(float(v), 2) for k, v in components.items()}
            })

        # ============================================================
        # 7b. NEWS SENTIMENT ADJUSTMENT (before Monte Carlo)
        # ============================================================
        news_cache = fetch_market_news()
        news_impact = news_cache['impact']
        news_articles = news_cache['articles'][:10]
        news_impact_pct = news_impact.get('price_impact_pct', 0)
        if news_impact_pct != 0:
            for pt in prediction:
                day = pt['day']
                decay = max(0.0, 1.0 - day / 60.0)
                adj_pct = news_impact_pct * decay
                if adj_pct != 0:
                    pt['price'] = round(pt['price'] * (1 + adj_pct / 100), 2)
                    pt['change_pct'] = round((pt['price'] / last_price - 1) * 100, 2)

        # ============================================================
        # 7c. GARCH(1,1) VOLATILITY FORECAST
        # ============================================================
        garch_omega, garch_alpha, garch_beta, garch_sigma2 = estimate_garch11(log_returns)
        garch_last_var = garch_sigma2[-1]
        garch_last_ret2 = log_returns[-1]**2
        # Forecast conditional variance for each day
        garch_forecast_var = np.zeros(forecast_days + 1)
        garch_forecast_var[0] = garch_last_var
        for d in range(1, forecast_days + 1):
            if d == 1:
                garch_forecast_var[d] = garch_omega + garch_alpha * garch_last_ret2 + garch_beta * garch_last_var
            else:
                garch_forecast_var[d] = garch_omega + (garch_alpha + garch_beta) * garch_forecast_var[d-1]
        garch_forecast_vol = np.sqrt(garch_forecast_var) * np.sqrt(252)  # annualized

        # ============================================================
        # 8. MONTE CARLO CONFIDENCE BANDS
        # ============================================================
        n_simulations = 1000
        sim_days = forecast_days
        dt = 1.0 / 252.0

        # Use regime-specific volatility (fallback)
        vol_multiplier = {'bull': 0.8, 'bear': 1.3, 'high_volatility': 1.5, 'sideways': 0.9}
        sim_vol = ewma_vol_daily * vol_multiplier.get(regime, 1.0)

        # Drift from composite forecast
        if len(prediction) >= 2:
            total_return = prediction[-1]['change_pct'] / 100 if prediction else 0
            annual_drift = total_return * (252.0 / max(forecast_days, 1))
        else:
            annual_drift = 0

        sim_paths = np.zeros((n_simulations, sim_days + 1))
        sim_paths[:, 0] = last_price

        np.random.seed(42)
        # Student's t with df=5 for fat tails (captures crash scenarios better)
        t_df = 5
        for sim in range(n_simulations):
            for d in range(1, sim_days + 1):
                z = np.random.standard_t(t_df)
                # Scale t-distribution to have unit variance: var(t_df) = df/(df-2)
                z = z / np.sqrt(t_df / (t_df - 2))
                # Use GARCH forecast vol for this day
                day_vol = np.sqrt(garch_forecast_var[min(d, forecast_days)]) if d <= forecast_days else sim_vol
                sim_paths[sim, d] = sim_paths[sim, d - 1] * np.exp(
                    (annual_drift - 0.5 * (day_vol * np.sqrt(252))**2) * dt
                    + day_vol * np.sqrt(252) * np.sqrt(dt) * z
                )

        # Calculate percentile bands
        p10 = np.percentile(sim_paths, 10, axis=0)
        p25 = np.percentile(sim_paths, 25, axis=0)
        p50 = np.percentile(sim_paths, 50, axis=0)
        p75 = np.percentile(sim_paths, 75, axis=0)
        p90 = np.percentile(sim_paths, 90, axis=0)

        # Attach bands to prediction
        for pt in prediction:
            day = pt['day']
            if day <= sim_days:
                pt['upper_80'] = round(float(p90[day]), 2)
                pt['upper_50'] = round(float(p75[day]), 2)
                pt['lower_50'] = round(float(p25[day]), 2)
                pt['lower_80'] = round(float(p10[day]), 2)
                # Legacy fields for backward compatibility
                pt['upper'] = pt['upper_50']
                pt['lower'] = pt['lower_50']
                pt['upper_pct'] = round((float(p75[day]) / last_price - 1) * 100, 2)
                pt['lower_pct'] = round((float(p25[day]) / last_price - 1) * 100, 2)
                pt['confidence'] = round(max(0, min(100, 100 - float(p75[day] - p25[day]) / last_price * 100 * 2)), 1)

        # ============================================================
        # 9. RISK METRICS
        # ============================================================
        # Max expected drawdown from Monte Carlo
        max_drawdowns = []
        for sim in range(n_simulations):
            path = sim_paths[sim]
            peak = np.maximum.accumulate(path)
            drawdown = (path - peak) / peak * 100
            max_drawdowns.append(float(np.min(drawdown)))
        expected_max_drawdown = round(float(np.mean(max_drawdowns)), 2)
        worst_drawdown = round(float(np.min(max_drawdowns)), 2)

        # Sharpe ratio of predicted path
        if len(prediction) > 1:
            pred_returns = []
            for i in range(1, len(prediction)):
                if prediction[i - 1]['price'] > 0:
                    pred_returns.append(prediction[i]['price'] / prediction[i - 1]['price'] - 1)
            if pred_returns and np.std(pred_returns) > 0:
                sharpe = float(np.mean(pred_returns) / np.std(pred_returns) * np.sqrt(252))
            else:
                sharpe = 0.0
        else:
            sharpe = 0.0

        # Probability of positive return at key horizons
        prob_positive = {}
        for horizon_day in [30, 60, 90, 180]:
            if horizon_day <= sim_days:
                positive_count = np.sum(sim_paths[:, horizon_day] > last_price)
                prob_positive[f'{horizon_day}d'] = round(float(positive_count / n_simulations * 100), 1)

        risk_metrics = {
            'expected_max_drawdown': expected_max_drawdown,
            'worst_case_drawdown': worst_drawdown,
            'sharpe_ratio': round(float(sharpe), 2),
            'prob_positive_return': prob_positive,
            'current_ewma_vol': round(float(ewma_vol_annual), 1),
            'vol_term_structure': round(float(vol_term_structure), 2),
        }

        # ============================================================
        # SUMMARY STATISTICS (要約統計)
        # ============================================================
        summary = OrderedDict()
        milestones = [('30d', 30), ('60d', 60), ('90d', 90), ('180d', 180)]
        for key, days in milestones:
            if days <= forecast_days and days <= sim_days:
                point = next((p for p in prediction if p['day'] >= days), None)
                if point:
                    pred_price = point['price']
                    sim_prices_at_day = sim_paths[:, days]
                    # 予測価格の±5%範囲に入る確率
                    band = pred_price * 0.05
                    prob_within_5 = float(np.sum(
                        (sim_prices_at_day >= pred_price - band) &
                        (sim_prices_at_day <= pred_price + band)
                    ) / n_simulations * 100)
                    # 予測価格の±10%範囲に入る確率
                    band10 = pred_price * 0.10
                    prob_within_10 = float(np.sum(
                        (sim_prices_at_day >= pred_price - band10) &
                        (sim_prices_at_day <= pred_price + band10)
                    ) / n_simulations * 100)
                    # 上昇確率
                    prob_up = float(np.sum(sim_prices_at_day > last_price) / n_simulations * 100)
                    # 予測価格以上になる確率
                    prob_above_pred = float(np.sum(sim_prices_at_day >= pred_price) / n_simulations * 100)
                    # 価格帯別確率分布（5分位）
                    p10_price = round(float(np.percentile(sim_prices_at_day, 10)), 2)
                    p25_price = round(float(np.percentile(sim_prices_at_day, 25)), 2)
                    p50_price = round(float(np.percentile(sim_prices_at_day, 50)), 2)
                    p75_price = round(float(np.percentile(sim_prices_at_day, 75)), 2)
                    p90_price = round(float(np.percentile(sim_prices_at_day, 90)), 2)
                    summary[key] = {
                        'change_pct': point['change_pct'],
                        'price': point['price'],
                        'prob_within_5pct': round(prob_within_5, 1),
                        'prob_within_10pct': round(prob_within_10, 1),
                        'prob_up': round(prob_up, 1),
                        'prob_above_pred': round(prob_above_pred, 1),
                        'price_dist': {
                            'p10': p10_price,
                            'p25': p25_price,
                            'p50': p50_price,
                            'p75': p75_price,
                            'p90': p90_price,
                        }
                    }

        # Year-end point
        year_end = datetime(datetime.now().year, 12, 31)
        days_to_year_end = (year_end - datetime.now()).days
        if 0 < days_to_year_end <= forecast_days and days_to_year_end <= sim_days:
            ye_point = next((p for p in prediction if p['day'] >= days_to_year_end), None)
            if ye_point:
                pred_price = ye_point['price']
                sim_prices_ye = sim_paths[:, days_to_year_end]
                band = pred_price * 0.05
                prob_within_5 = float(np.sum(
                    (sim_prices_ye >= pred_price - band) &
                    (sim_prices_ye <= pred_price + band)
                ) / n_simulations * 100)
                band10 = pred_price * 0.10
                prob_within_10 = float(np.sum(
                    (sim_prices_ye >= pred_price - band10) &
                    (sim_prices_ye <= pred_price + band10)
                ) / n_simulations * 100)
                prob_up = float(np.sum(sim_prices_ye > last_price) / n_simulations * 100)
                prob_above_pred = float(np.sum(sim_prices_ye >= pred_price) / n_simulations * 100)
                p10_price = round(float(np.percentile(sim_prices_ye, 10)), 2)
                p25_price = round(float(np.percentile(sim_prices_ye, 25)), 2)
                p50_price = round(float(np.percentile(sim_prices_ye, 50)), 2)
                p75_price = round(float(np.percentile(sim_prices_ye, 75)), 2)
                p90_price = round(float(np.percentile(sim_prices_ye, 90)), 2)
                summary['year_end'] = {
                    'change_pct': ye_point['change_pct'],
                    'price': ye_point['price'],
                    'prob_within_5pct': round(prob_within_5, 1),
                    'prob_within_10pct': round(prob_within_10, 1),
                    'prob_up': round(prob_up, 1),
                    'prob_above_pred': round(prob_above_pred, 1),
                    'price_dist': {
                        'p10': p10_price,
                        'p25': p25_price,
                        'p50': p50_price,
                        'p75': p75_price,
                        'p90': p90_price,
                    }
                }

        # Current trend (30d)
        recent_prices = [d['close'] for d in current_data[-30:]] if len(current_data) >= 30 else [d['close'] for d in current_data]
        current_trend = (recent_prices[-1] / recent_prices[0] - 1) * 100 if recent_prices[0] != 0 else 0

        # ============================================================
        # MODEL COMPONENTS BREAKDOWN (モデル要素分解)
        # ============================================================
        # Show each component's contribution at 30d and 90d for transparency
        model_components = {
            'weights': {
                'historical_patterns': W_HIST,
                'mean_reversion': W_MR,
                'momentum': W_MOM,
                'cross_asset': W_CROSS,
                'regime_adjustment': W_REGIME
            },
            'at_30d': {},
            'at_90d': {},
        }
        for label, day_target in [('at_30d', 30), ('at_90d', 90)]:
            if day_target <= forecast_days:
                model_components[label] = {
                    'historical': round(historical_forecasts.get(day_target, 0), 2),
                    'mean_reversion': round(mr_forecasts.get(day_target, 0), 2),
                    'momentum': round(momentum_forecasts.get(day_target, 0), 2),
                    'cross_asset': round(cross_asset_forecasts.get(day_target, 0), 2),
                    'regime': round(regime_forecasts.get(day_target, 0), 2),
                }

        # Technical indicators for frontend display
        technical_indicators = {
            'rsi_14': round(rsi_14, 1),
            'rsi_signal': 'overbought' if rsi_14 > 70 else ('oversold' if rsi_14 < 30 else 'neutral'),
            'macd_histogram': round(float(macd_histogram), 4),
            'macd_signal': 'bullish' if macd_histogram > 0 else 'bearish',
            'roc_5d': round(roc_5, 2),
            'roc_10d': round(roc_10, 2),
            'roc_20d': round(roc_20, 2),
            'roc_60d': round(roc_60, 2),
            'momentum_score': round(float(momentum_score), 1),
            'sma_50': round(float(sma_50[-1]), 2),
            'sma_200': round(float(sma_200[-1]), 2),
            'ma_cross_signal': round(float(ma_cross_signal), 2),
            'bollinger_width': round(bb_width, 2),
            'bollinger_percentile': round(bb_percentile * 100, 1),
            'mean_reversion_half_life_days': round(float(half_life * 252), 1),
            'ou_theta': round(float(theta), 4),
            'ou_mu_price': round(float(np.exp(mu_ou)), 2),
        }

        # FRED macro indicators (optional)
        fred_data = fetch_fred_indicators()

        # ============================================================
        # API RESPONSE
        # ============================================================
        return jsonify({
            'symbol': symbol,
            'last_price': last_price,
            'last_date': last_date,
            'current_trend': round(float(current_trend), 2),
            'current_volatility': current_volatility,
            'regime': {
                'classification': regime,
                'label': regime_label,
                'ma_cross_signal': round(float(ma_cross_signal), 2),
                'bollinger_width': round(bb_width, 2),
            },
            'factors': factors,
            'cross_asset_signals': cross_asset_signals,
            'technical_indicators': technical_indicators,
            'model_components': model_components,
            'risk_metrics': risk_metrics,
            'prediction': prediction,
            'summary': summary,
            'contributing_events': [{
                'event_id': p['event_id'],
                'event_name': p['event_name'],
                'category': p['category'],
                'start_date': p['start_date'],
                'score': p['score'],
                'max_drawdown': p['max_drawdown'],
                'final_change': p['final_change'],
                'outcome': p['outcome']
            } for p in top_patterns],
            'current_data': current_data,
            'forecast_days': forecast_days,
            'news_impact': news_impact,
            'recent_news': news_articles,
            'fred_indicators': fred_data,
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/news')
def get_news():
    """Return cached market news with sentiment impact"""
    cache = fetch_market_news()
    return jsonify({
        'articles': cache['articles'],
        'impact': cache['impact'],
        'fetched_at': datetime.fromtimestamp(cache['timestamp']).strftime('%H:%M:%S') if cache['timestamp'] else None
    })


# ============================================================
# FEATURE 3: PREDICTION ACCURACY TRACKING (予測精度追跡)
# ============================================================
PREDICTIONS_FILE = os.path.join(os.path.dirname(__file__), 'data', 'predictions_history.json')


def _load_predictions_history():
    if os.path.exists(PREDICTIONS_FILE):
        try:
            with open(PREDICTIONS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save_predictions_history(history):
    try:
        with open(PREDICTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(history[-100:], f, ensure_ascii=False, indent=2)  # Keep last 100
    except Exception as e:
        print(f"[PredHistory] Save error: {e}")


@app.route('/api/predictions/save', methods=['POST'])
def save_prediction():
    """Save a prediction snapshot for later accuracy comparison"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data'}), 400

    record = {
        'id': datetime.now().strftime('%Y%m%d%H%M%S'),
        'saved_at': datetime.now().isoformat(),
        'symbol': data.get('symbol', ''),
        'last_price': data.get('last_price', 0),
        'last_date': data.get('last_date', ''),
        'regime': data.get('regime', ''),
        'summary': data.get('summary', {}),
    }

    history = _load_predictions_history()
    history.append(record)
    _save_predictions_history(history)

    return jsonify({'status': 'saved', 'id': record['id']})


@app.route('/api/predictions/history')
def get_predictions_history():
    """Return past predictions with accuracy comparison"""
    history = _load_predictions_history()
    results = []

    for record in history:
        symbol = record.get('symbol', '^GSPC')
        saved_date = record.get('last_date', '')
        summary = record.get('summary', {})

        # Fetch current price for comparison
        accuracy = {}
        for period_key, pred_data in summary.items():
            if not isinstance(pred_data, dict):
                continue
            pred_price = pred_data.get('price', 0)
            if not pred_price:
                continue

            # Calculate days since prediction
            try:
                saved_dt = datetime.strptime(saved_date, '%Y-%m-%d')
                days_elapsed = (datetime.now() - saved_dt).days
                target_days = {'30d': 30, '60d': 60, '90d': 90, '180d': 180, 'year_end': (datetime(saved_dt.year, 12, 31) - saved_dt).days}
                td = target_days.get(period_key, 0)
                if td and days_elapsed >= td:
                    # Period has elapsed - get actual price
                    try:
                        target_date = saved_dt + timedelta(days=td)
                        ticker = yf.Ticker(symbol)
                        hist = ticker.history(start=(target_date - timedelta(days=3)).strftime('%Y-%m-%d'),
                                              end=(target_date + timedelta(days=3)).strftime('%Y-%m-%d'))
                        if not hist.empty:
                            actual_price = round(float(hist['Close'].iloc[-1]), 2)
                            error_pct = round((pred_price - actual_price) / actual_price * 100, 2)
                            accuracy[period_key] = {
                                'predicted': pred_price,
                                'actual': actual_price,
                                'error_pct': error_pct,
                                'status': 'verified'
                            }
                        else:
                            accuracy[period_key] = {'predicted': pred_price, 'status': 'no_data'}
                    except Exception:
                        accuracy[period_key] = {'predicted': pred_price, 'status': 'error'}
                else:
                    accuracy[period_key] = {'predicted': pred_price, 'status': 'pending', 'days_remaining': max(0, td - days_elapsed)}
            except Exception:
                pass

        results.append({**record, 'accuracy': accuracy})

    return jsonify(results)


# ============================================================
# FEATURE 4: MARKET ALERTS (マーケットアラート)
# ============================================================
@app.route('/api/alerts')
def get_alerts():
    """Generate real-time market alerts based on current conditions"""
    symbol = request.args.get('symbol', '^GSPC')

    alerts = []

    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period='3mo')
        if hist.empty:
            return jsonify([])

        closes = np.array(hist['Close'].values, dtype=float)
        n = len(closes)

        # 1. RSI alerts
        if n > 14:
            deltas = np.diff(closes)
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            avg_gain = np.mean(gains[-14:])
            avg_loss = np.mean(losses[-14:])
            rsi = 100 - (100 / (1 + avg_gain / avg_loss)) if avg_loss > 0 else 100
            if rsi > 75:
                alerts.append({'type': 'warning', 'icon': '⚠️', 'title': 'RSI過熱警告', 'message': f'RSI={rsi:.1f}  買われすぎ圏。短期調整リスクが上昇。', 'priority': 2})
            elif rsi < 25:
                alerts.append({'type': 'opportunity', 'icon': '💡', 'title': 'RSI売られすぎ', 'message': f'RSI={rsi:.1f}  売られすぎ圏。反発の可能性。', 'priority': 2})

        # 2. Large daily move
        if n >= 2:
            daily_change = (closes[-1] / closes[-2] - 1) * 100
            if abs(daily_change) > 2:
                direction = '急騰' if daily_change > 0 else '急落'
                alerts.append({'type': 'danger' if daily_change < -2 else 'info', 'icon': '🔥', 'title': f'大幅{direction}',
                               'message': f'直近の終値変動: {daily_change:+.2f}%', 'priority': 3})

        # 3. Volatility spike
        if n > 20:
            recent_vol = float(np.std(np.diff(np.log(closes[-10:]))) * np.sqrt(252) * 100)
            normal_vol = float(np.std(np.diff(np.log(closes[-60:]))) * np.sqrt(252) * 100) if n > 60 else recent_vol
            if recent_vol > normal_vol * 1.5 and recent_vol > 20:
                alerts.append({'type': 'warning', 'icon': '📊', 'title': 'ボラティリティ急上昇',
                               'message': f'短期ボラ {recent_vol:.1f}% vs 通常 {normal_vol:.1f}%（{recent_vol/normal_vol:.1f}倍）', 'priority': 2})

        # 4. Golden / Death cross
        if n > 200:
            sma50 = np.mean(closes[-50:])
            sma200 = np.mean(closes[-200:])
            sma50_prev = np.mean(closes[-51:-1])
            sma200_prev = np.mean(closes[-201:-1])
            if sma50_prev < sma200_prev and sma50 > sma200:
                alerts.append({'type': 'opportunity', 'icon': '✨', 'title': 'ゴールデンクロス', 'message': '50日移動平均が200日移動平均を上抜け。強気シグナル。', 'priority': 3})
            elif sma50_prev > sma200_prev and sma50 < sma200:
                alerts.append({'type': 'danger', 'icon': '💀', 'title': 'デスクロス', 'message': '50日移動平均が200日移動平均を下抜け。弱気シグナル。', 'priority': 3})

        # 5. Drawdown from recent high
        if n > 5:
            recent_high = float(np.max(closes[-60:])) if n >= 60 else float(np.max(closes))
            drawdown = (closes[-1] / recent_high - 1) * 100
            if drawdown < -10:
                alerts.append({'type': 'danger', 'icon': '📉', 'title': '大幅ドローダウン',
                               'message': f'直近高値から {drawdown:.1f}% 下落中。', 'priority': 3})
            elif drawdown < -5:
                alerts.append({'type': 'warning', 'icon': '📉', 'title': '調整局面', 'message': f'直近高値から {drawdown:.1f}% 下落。', 'priority': 1})

        # 6. News impact alert
        news = fetch_market_news()
        impact = news.get('impact', {})
        if abs(impact.get('price_impact_pct', 0)) > 0.5:
            direction = '強気' if impact['price_impact_pct'] > 0 else '弱気'
            alerts.append({'type': 'info', 'icon': '📰', 'title': f'ニュースセンチメント: {direction}',
                           'message': f'推定影響: {impact["price_impact_pct"]:+.2f}%（{impact.get("article_count", 0)}件分析）', 'priority': 1})

    except Exception as e:
        alerts.append({'type': 'info', 'icon': 'ℹ️', 'title': 'アラート取得エラー', 'message': str(e), 'priority': 0})

    alerts.sort(key=lambda x: x.get('priority', 0), reverse=True)
    return jsonify(alerts)


# ============================================================
# FEATURE 5: CSV EXPORT (CSV出力)
# ============================================================
from flask import Response
import csv
import io


@app.route('/api/export/csv')
def export_csv():
    """Export prediction summary as CSV"""
    symbol = request.args.get('symbol', '^GSPC')
    data_json = request.args.get('data', '')

    if not data_json:
        return jsonify({'error': 'No data provided'}), 400

    try:
        data = json.loads(data_json)
    except Exception:
        return jsonify({'error': 'Invalid JSON'}), 400

    output = io.StringIO()
    output.write('\ufeff')  # BOM for Excel UTF-8
    writer = csv.writer(output)

    # Header
    writer.writerow(['予測レポート', '', '', ''])
    writer.writerow(['シンボル', symbol, '基準日', data.get('last_date', '')])
    writer.writerow(['現在値', data.get('last_price', ''), 'レジーム', data.get('regime', '')])
    writer.writerow([])

    # Summary
    writer.writerow(['期間', '予測価格', '変化率(%)', '上昇確率(%)', '±5%圏確率(%)', '±10%圏確率(%)', 'P10', 'P25', 'P50(中央値)', 'P75', 'P90'])
    summary = data.get('summary', {})
    period_labels = {'30d': '30日後', '60d': '60日後', '90d': '3ヶ月後', '180d': '6ヶ月後', 'year_end': '年末'}
    for key in ['30d', '60d', '90d', '180d', 'year_end']:
        if key in summary:
            s = summary[key]
            dist = s.get('price_dist', {})
            writer.writerow([
                period_labels.get(key, key), s.get('price', ''), s.get('change_pct', ''),
                s.get('prob_up', ''), s.get('prob_within_5pct', ''), s.get('prob_within_10pct', ''),
                dist.get('p10', ''), dist.get('p25', ''), dist.get('p50', ''), dist.get('p75', ''), dist.get('p90', '')
            ])

    writer.writerow([])

    # Technical indicators
    tech = data.get('technical_indicators', {})
    if tech:
        writer.writerow(['テクニカル指標', '値'])
        for k, v in tech.items():
            writer.writerow([k, v])

    writer.writerow([])

    # Risk metrics
    risk = data.get('risk_metrics', {})
    if risk:
        writer.writerow(['リスク指標', '値'])
        for k, v in risk.items():
            if isinstance(v, dict):
                for kk, vv in v.items():
                    writer.writerow([f'{k}_{kk}', vv])
            else:
                writer.writerow([k, v])

    content = output.getvalue()
    return Response(content, mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename=prediction_{symbol}_{datetime.now().strftime("%Y%m%d")}.csv'})


if __name__ == '__main__':
    app.run(debug=True, port=5050)
