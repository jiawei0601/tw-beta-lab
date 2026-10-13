"""Pass only a fixed source snapshot to an isolated no-tools Claude review."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
out = root / '.review'
out.mkdir(exist_ok=True)
files = ['beta.py', 'server.py', 'web/index.html', 'web/app.js', 'web/style.css',
         'tests/test_beta.py', 'README.md', 'HANDOFF.md']
parts = []
for name in files:
    text = (root / name).read_text(encoding='utf-8')
    parts.append('\nFILE: ' + name + '\n' + '\n'.join(f'{i}: {line}' for i, line in enumerate(text.splitlines(), 1)))
snapshot = '\n'.join(parts)
digest = hashlib.sha256(snapshot.encode()).hexdigest()
(out / 'snapshot.txt').write_text(snapshot, encoding='utf-8')
(out / 'snapshot.sha256').write_text(digest, encoding='utf-8')
config = out / 'empty-mcp.json'
config.write_text(json.dumps({'mcpServers': {}}), encoding='utf-8')
if '--send' not in sys.argv:
    print('Prepared local review snapshot:', digest)
    print('External review requires explicit user authorization, then --send.')
    sys.exit(0)
prompt = '''Perform a formal independent correctness/security review. Personally inspect the supplied fixed snapshot; do not delegate. Tools are disabled. This is newly written code, not a conversation history. No file writes or external actions. Scope: local Taiwan stock/ETF Beta calculator, historical alignment, OLS, public Yahoo price data, user inputs, CSV and UI flow. Required verdict: PASS / RETURN / CANNOT_DETERMINE. Cite file:line, concrete trigger and consequence for defects. Distinguish blocking defects from suggestions. Do not assume any test passed solely from HANDOFF; inspect test logic. Runtime tests are performed separately by the author. The accepted scope is local-only with separate price/^TWII and adjclose/0050 proxy modes. Report actual model identifier if available. Snapshot SHA256: ''' + digest + '\n' + snapshot
exe = Path(os.environ['APPDATA']) / 'npm/node_modules/@anthropic-ai/claude-code/bin/claude.exe'
env = dict(os.environ)
env.pop('CLAUDECODE', None)
result = subprocess.run([str(exe), '-p', '--tools', '', '--strict-mcp-config', '--mcp-config', str(config),
                         '--disable-slash-commands', '--no-session-persistence', '--output-format', 'json'],
                        input=prompt, text=True, encoding='utf-8', capture_output=True, cwd=out, env=env, timeout=240)
(out / 'response.json').write_text(result.stdout, encoding='utf-8')
(out / 'stderr.txt').write_text(result.stderr, encoding='utf-8')
print('Snapshot:', digest, 'Exit:', result.returncode)
try:
    data = json.loads(result.stdout)
    print(json.dumps({k: data.get(k) for k in ('is_error','result','modelUsage')}, ensure_ascii=False))
except ValueError:
    print(result.stderr[:1000] or result.stdout[:1000])
