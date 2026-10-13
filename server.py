"""Local-only Beta research tool. Python 3.12+, standard library only."""
import argparse
import json
import math
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from beta import aligned_returns, regress

ROOT = Path(__file__).resolve().parent
TZ = timezone(timedelta(hours=8))
CACHE = {}
LOCK = threading.Lock()


def fetch(symbol, start, end, adjusted=False):
    cache_key = (symbol, str(start), str(end), adjusted)
    with LOCK:
        cached = CACHE.get(cache_key)
    if cached and time.time() - cached[0] < 3600:
        return cached[1]
    def stamp(d):
        return int(datetime(d.year, d.month, d.day, tzinfo=TZ).timestamp())
    params = urllib.parse.urlencode({'period1': stamp(start), 'period2': stamp(end + timedelta(days=1)),
                                    'interval': '1d', 'events': 'div,splits'})
    url = 'https://query1.finance.yahoo.com/v8/finance/chart/' + urllib.parse.quote(symbol, safe='') + '?' + params
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=22) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise ValueError(f'查無 {symbol}') from exc
        raise ValueError(f'行情服務 HTTP {exc.code}，請稍後重試。') from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ValueError('無法連線行情服務，請確認網路或稍後重試。') from exc
    result = data.get('chart', {}).get('result')
    if not result:
        raise ValueError(f'{symbol} 沒有可用行情')
    q = result[0]
    indicators = q.get('indicators', {})
    if adjusted:
        blocks = indicators.get('adjclose')
        if not blocks or not blocks[0].get('adjclose'):
            raise ValueError(f'{symbol} 缺少調整價，不能改用未調整價代算。')
        prices = blocks[0]['adjclose']
    else:
        prices = indicators.get('quote', [{}])[0].get('close', [])
    series = {}
    for ts, value in zip(q.get('timestamp', []), prices):
        if value is not None and math.isfinite(value) and value > 0:
            ds = datetime.fromtimestamp(ts, TZ).date().isoformat()
            series[ds] = value
    if not series:
        raise ValueError(f'{symbol} 在指定期間沒有有效價格')
    meta = q.get('meta', {})
    item = {'symbol': symbol, 'name': meta.get('longName') or meta.get('shortName') or symbol,
            'series': series, 'fetched_at': datetime.now(TZ).isoformat(timespec='seconds')}
    with LOCK:
        if len(CACHE) > 256:
            CACHE.clear()
        CACHE[cache_key] = (time.time(), item)
    return item


def calculate(payload):
    today = datetime.now(TZ).date()
    start = date.fromisoformat(payload.get('start', ''))
    end = date.fromisoformat(payload.get('end', ''))
    if end < start or end > today or (end - start).days > 366 * 10:
        raise ValueError('日期需由早到晚、不得超過今天，且期間上限為 10 年。')
    frequency = payload.get('frequency', 'daily')
    if frequency not in ('daily', 'weekly', 'monthly'):
        raise ValueError('不支援的報酬頻率')
    annual_rf = float(payload.get('rf', 0)) / 100
    if not math.isfinite(annual_rf) or not 0 <= annual_rf <= .2:
        raise ValueError('無風險年利率需介於 0% 與 20%。')
    mode = payload.get('mode', 'price')
    if mode not in ('price', 'adjusted'):
        raise ValueError('不支援的價格口徑')
    codes = list(dict.fromkeys(re.split(r'[\s,，、]+', str(payload.get('codes', '')).strip().upper())))
    if not 1 <= len(codes) <= 8 or any(not re.fullmatch(r'\d{4,6}[A-Z]?(?:\.(?:TW|TWO))?', code) for code in codes):
        raise ValueError('請輸入 1–8 檔台股代號，以逗號或空白分隔；可指定 .TW 或 .TWO。')
    adjusted = mode == 'adjusted'
    benchmark_symbol = '0050.TW' if adjusted else '^TWII'
    market = fetch(benchmark_symbol, start, end, adjusted)

    def one(code):
        try:
            candidates = [code] if '.' in code else [code + '.TW', code + '.TWO']
            stock = None
            last = None
            for candidate in candidates:
                try:
                    stock = fetch(candidate, start, end, adjusted)
                    break
                except ValueError as exc:
                    last = exc
                    if not str(exc).startswith('查無 '):
                        raise
            if stock is None:
                raise last
            rows, rejected = aligned_returns(stock['series'], market['series'], start, end, frequency, today)
            stats = regress(rows, annual_rf, frequency)
            warnings = []
            if stats['n'] < 30:
                warnings.append('樣本少於 30 筆，估計容易受個別觀測值影響。')
            if (end - date.fromisoformat(stats['to'])).days > {'daily': 7, 'weekly': 14, 'monthly': 40}[frequency]:
                warnings.append('最後有效資料明顯早於查詢結束日；請確認是否停牌、下市或來源延遲。')
            return dict(stats, code=code, symbol=stock['symbol'], name=stock['name'],
                        fetched_at=stock['fetched_at'], rejected=rejected, warnings=warnings)
        except ValueError as exc:
            return {'code': code, 'error': str(exc)}
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(one, codes))
    return {'results': results, 'benchmark': benchmark_symbol, 'mode': mode, 'frequency': frequency,
            'rf_annual': annual_rf, 'start': str(start), 'end': str(end),
            'benchmark_fetched_at': market['fetched_at'], 'source': 'Yahoo Finance chart',
            'note': '各標的使用各自與基準的共同有效期間；比較時請同時查看起訖日與樣本數。'}


class Handler(BaseHTTPRequestHandler):
    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == '/api/health':
            return self.send_json({'status': 'ok', 'today': str(datetime.now(TZ).date())})
        files = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}
        if path not in files:
            return self.send_error(404)
        file = ROOT / 'web' / files[path]
        body = file.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', {'html': 'text/html; charset=utf-8', 'js': 'text/javascript; charset=utf-8',
                                       'css': 'text/css; charset=utf-8'}[file.suffix[1:]])
        self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != '/api/calculate':
            return self.send_error(404)
        # Reject cross-origin requests and DNS-rebinding hosts. No CORS enabled.
        host = self.headers.get('Host', '')
        allowed = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
        origin = self.headers.get('Origin')
        if host not in allowed or (origin and origin not in {'http://' + h for h in allowed}):
            return self.send_json({'error': '僅接受本機同源請求'}, 403)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 8192:
                raise ValueError('請求大小不正確')
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError('請求格式不正確')
            return self.send_json(calculate(payload))
        except (ValueError, TypeError, OverflowError) as exc:
            return self.send_json({'error': str(exc)}, 400)
        except Exception:
            return self.send_json({'error': '計算服務發生錯誤；請稍後再試。'}, 500)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--open-browser', action='store_true')
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'Taiwan Beta Lab: http://127.0.0.1:{args.port}', flush=True)
    if args.open_browser:
        webbrowser.open(f'http://127.0.0.1:{args.port}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
