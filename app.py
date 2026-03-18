from flask import Flask, render_template, jsonify, request
import json
import os
import yfinance as yf
from datetime import datetime, timedelta
import numpy as np

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

        # Regime classification
        if ma_cross_signal > 1.0 and bb_width < 8:
            regime = 'bull'
            regime_label = 'Bull (強気相場)'
        elif ma_cross_signal < -1.0 and bb_width < 8:
            regime = 'bear'
            regime_label = 'Bear (弱気相場)'
        elif bb_width >= 8:
            regime = 'high_volatility'
            regime_label = 'High Volatility (高ボラティリティ)'
        else:
            regime = 'sideways'
            regime_label = 'Sideways (レンジ相場)'

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
        # RSI (14-day)
        def calc_rsi(prices, period=14):
            if len(prices) < period + 1:
                return 50.0
            deltas = np.diff(prices)
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            avg_gain = np.mean(gains[-period:])
            avg_loss = np.mean(losses[-period:])
            if avg_loss == 0:
                return 100.0
            rs = avg_gain / avg_loss
            return float(100 - (100 / (1 + rs)))

        rsi_14 = calc_rsi(closes, 14)

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

        # Momentum daily forecast (annualized)
        momentum_annual_pct = np.clip(momentum_score * 0.3, -50, 50)
        momentum_forecasts = {}
        for day in range(0, forecast_days + 1):
            # Momentum decays over time (short-term signal)
            decay = np.exp(-day / 30.0)
            momentum_forecasts[day] = float(momentum_annual_pct * (day / 252.0) * decay)

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
        for event in EVENTS_DATA['events']:
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
        # Weights: Historical 35%, Mean Reversion 20%, Momentum 15%,
        #          Cross-Asset 15%, Regime Adjustment 15%
        W_HIST = 0.35
        W_MR = 0.20
        W_MOM = 0.15
        W_CROSS = 0.15
        W_REGIME = 0.15

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
        # 8. MONTE CARLO CONFIDENCE BANDS
        # ============================================================
        n_simulations = 500
        sim_days = forecast_days
        dt = 1.0 / 252.0

        # Use regime-specific volatility
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
        for sim in range(n_simulations):
            for d in range(1, sim_days + 1):
                z = np.random.standard_normal()
                sim_paths[sim, d] = sim_paths[sim, d - 1] * np.exp(
                    (annual_drift - 0.5 * (sim_vol * np.sqrt(252))**2) * dt
                    + sim_vol * np.sqrt(252) * np.sqrt(dt) * z
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
            'forecast_days': forecast_days
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5050)
