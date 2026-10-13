"""Deterministic aligned-return OLS; no market-data dependencies."""
import math
from datetime import date, timedelta
from statistics import mean


def period_key(d, frequency):
    if frequency == 'daily':
        return d.isoformat()
    if frequency == 'weekly':
        y, w, _ = d.isocalendar()
        return f'{y}-W{w:02d}'
    return d.strftime('%Y-%m')


def aligned_returns(stock, market, start, end, frequency, today=None):
    """Only use endpoints actually present in BOTH series. Never forward-fill.

    Daily gaps are rejected unless both sources have the same consecutive pair.
    Weekly/monthly periods with different observed last dates are rejected.
    Missing intermediate periods cannot be turned into a one-period return.
    """
    today = today or date.today()
    if frequency not in ('daily', 'weekly', 'monthly'):
        raise ValueError('不支援的報酬頻率')
    def aggregate(series):
        groups = {}
        for ds, value in sorted(series.items()):
            d = date.fromisoformat(ds)
            if d >= today or d > end or not math.isfinite(value) or value <= 0:
                continue
            key = period_key(d, frequency)
            if frequency != 'daily' and key == period_key(today, frequency):
                continue
            # A historical query ending mid-period must not produce a partial bar.
            if frequency == 'weekly' and d + timedelta(days=6-d.weekday()) > end:
                continue
            if frequency == 'monthly':
                next_month = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
                if next_month - timedelta(days=1) > end:
                    continue
            groups[key] = (d, value)
        return groups
    s, m = aggregate(stock), aggregate(market)
    sk, mk = sorted(s), sorted(m)
    sprev = {sk[i]: sk[i-1] for i in range(1, len(sk))}
    mprev = {mk[i]: mk[i-1] for i in range(1, len(mk))}
    rows = []
    rejected = 0
    for key in sorted(set(s) & set(m)):
        if s[key][0] < start:
            continue
        previous = sprev.get(key)
        if not previous or previous != mprev.get(key) or previous not in m:
            rejected += 1
            continue
        d, sv = s[key]
        md, mv = m[key]
        pd, psv = s[previous]
        pmd, pmv = m[previous]
        if d != md or pd != pmd or pd < start:
            rejected += 1
            continue
        if frequency == 'weekly' and (d - pd).days > 10:
            rejected += 1
            continue
        if frequency == 'monthly' and (d.year * 12 + d.month) - (pd.year * 12 + pd.month) != 1:
            rejected += 1
            continue
        rows.append({'date': d.isoformat(), 'from': pd.isoformat(),
                     'stock': sv / psv - 1, 'market': mv / pmv - 1})
    return rows, rejected


def regress(rows, annual_rf=0, frequency='daily'):
    n = len(rows)
    if n < 12:
        raise ValueError(f'有效樣本只有 {n} 筆，至少需要 12 筆；請延長期間或改用日報酬。')
    periods = {'daily': 252, 'weekly': 52, 'monthly': 12}[frequency]
    rf = (1 + annual_rf) ** (1 / periods) - 1
    x = [r['market'] - rf for r in rows]
    y = [r['stock'] - rf for r in rows]
    xm, ym = mean(x), mean(y)
    xx = sum((v - xm) ** 2 for v in x)
    yy = sum((v - ym) ** 2 for v in y)
    if xx < 1e-20:
        raise ValueError('基準報酬沒有足夠變化，無法計算 Beta。')
    xy = sum((a - xm) * (b - ym) for a, b in zip(x, y))
    beta = xy / xx
    intercept = ym - beta * xm
    sse = sum((b - intercept - beta * a) ** 2 for a, b in zip(x, y))
    se = math.sqrt(max(0, sse / (n - 2) / xx))
    return {'beta': beta, 'intercept': intercept, 'r2': xy ** 2 / (xx * yy) if yy > 1e-20 else 0,
            'correlation': xy / math.sqrt(xx * yy) if yy > 1e-20 else 0,
            'beta_se': se, 'n': n, 'rf_period': rf,
            'from': rows[0]['from'], 'to': rows[-1]['date'],
            'points': [dict(r, x=a, y=b) for r, a, b in zip(rows, x, y)]}
