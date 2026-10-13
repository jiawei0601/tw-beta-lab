"""HTTP real-data and security smoke; persist evidence without fake quotes."""
import json
from pathlib import Path
import urllib.request
import urllib.error

base = 'http://127.0.0.1:8765'
def post(payload, origin=None):
    headers = {'Content-Type':'application/json'}
    if origin:
        headers['Origin'] = origin
    request = urllib.request.Request(base+'/api/calculate', data=json.dumps(payload).encode(), headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=100) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc)

evidence = []
for frequency, mode, codes in [('daily','price','2330 0050 00878 6488'),('weekly','price','2330'),('monthly','price','2330'),('monthly','adjusted','0050 00631L')]:
    payload={'codes':codes,'start':'2023-10-13','end':'2026-10-13','frequency':frequency,'mode':mode}
    status,data=post(payload)
    evidence.append({'request':payload,'status':status,'data':data})
    print(frequency,mode,status,[(r.get('symbol',r['code']),round(r.get('beta',0),5),r.get('n'),r.get('error')) for r in data.get('results',[])])
    assert status==200 and all('error' not in r for r in data['results']), data
    if mode=='adjusted':
        assert abs(data['results'][0]['beta']-1)<1e-10
        assert abs(data['results'][0]['intercept'])<1e-10
assert post({'codes':'../../x','start':'2025-01-01','end':'2025-02-01'})[0]==400
assert post({'codes':'2330'},'https://untrusted.invalid')[0]==403
out=Path(__file__).resolve().parents[1]/'evidence'
out.mkdir(exist_ok=True)
(out/'live-smoke.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
print('Real-data, identity Beta, input validation, cross-origin rejection: PASS')
