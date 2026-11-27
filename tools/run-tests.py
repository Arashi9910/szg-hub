"""平行跑 e2e 測試（每支在自己的網路命名空間裡，見 tools/isotest.sh）。
用法：python3 tools/run-tests.py [-j 2] [測試檔或關鍵字 ...]
  不給檔案＝全部 tests/e2e_*.py 和 tests/unit_*.py
  -j：同時跑幾支（預設 2；這台 2 核心、7GB，Chromium 很吃資源，別開太多）
每支的輸出存在 tests/.logs/<名字>.log，最後印出 ✓／✗ 和失敗的那幾行。"""
import argparse, glob, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser(); ap.add_argument('-j', type=int, default=2); ap.add_argument('tests', nargs='*')
a = ap.parse_args()
allt = sorted(glob.glob(os.path.join(ROOT, 'tests', 'e2e_*.py')) + glob.glob(os.path.join(ROOT, 'tests', 'unit_*.py')))
pick = [t for t in allt if not a.tests or any(k in os.path.basename(t) for k in a.tests)]
os.makedirs(os.path.join(ROOT, 'tests', '.logs'), exist_ok=True)
def run(t):
    name = os.path.basename(t)[:-3]; log = os.path.join(ROOT, 'tests', '.logs', name + '.log'); t0 = time.time()
    with open(log, 'w') as f:
        rc = subprocess.call([os.path.join(ROOT, 'tools', 'isotest.sh'), os.path.relpath(t, ROOT)], cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    out = open(log, encoding='utf-8', errors='replace').read()
    ok = rc == 0 and '全部通過' in out
    print(('✓' if ok else '✗'), name, f'{time.time() - t0:.0f}s', flush=True)
    return name, ok, out
with ThreadPoolExecutor(a.j) as ex: res = list(ex.map(run, pick))
bad = [r for r in res if not r[1]]
for name, _, out in bad:
    print(f'\n--- {name} ---'); print('\n'.join([l for l in out.splitlines() if '✗' in l or 'Error' in l or 'Traceback' in l][:15]))
print(f'\n{len(res) - len(bad)}/{len(res)} 通過'); sys.exit(1 if bad else 0)
