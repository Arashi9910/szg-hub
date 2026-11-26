"""自動強化（v0.71.4）：每次確認＝建立待確認工作；每日上限內自動＝上限內直接衝、超過等確認；詛咒卷軸一律等確認；衝過的不再衝"""
import asyncio, json, sys, time
from harness import Env, hub_json, http, HUB, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)
def mock_char(a, c): return json.loads(http('GET', MOCK + '/__mock/state')[1])['accounts'][a]['chars'][c]
def forge_jobs(): return [j for j in hub_json('GET', '/api/data')['jobs'] if j['kind'] == 'forge']
async def wait(fn, sec=30, step=1):
    end = time.time() + sec
    while time.time() < end:
        v = fn()
        if v: return v
        await asyncio.sleep(step)
    return None

RULE = {'id': 'r1', 'on': True, 'charId': 'c1', 'gearName': '工地手套', 'item': 'i2040801', 'count': 'all', 'stopAfter': 0, 'stopOnFail': False, 'minSucc': 2}

async def main():
    async with Env() as env:
        await env.open_accounts(['A1'])
        await env.wait_chars(1)
        await wait(lambda: (hub_json('GET', '/api/world') or {}).get('scrolls'), 30)

        print('1. 每次確認：建立待確認的工作')
        hub_json('POST', '/api/settings', {'forgeAuto': {'mode': 'confirm', 'everyMin': 30, 'dailyCap': 0, 'rules': [RULE]}})
        r = hub_json('POST', '/api/forge/auto-run', {})
        js = forge_jobs()
        check(len(js) == 1 and js[0]['status'] == 'pending' and js[0].get('auto'), f"建立 1 個待確認的強化工作（{[(j['status'], j.get('auto')) for j in js]}）")
        g = js and js[0]['batches'][0]['gear']
        check(g and len(g) == 2 and js[0]['estimate'] == 1000000, f"卷軸 12 張：每件 5 次，只排得下 2 件、最多 100 萬（{len(g or [])} 件、{js and js[0]['estimate']}）")
        check(any('等你確認' in l['msg'] for l in r['autoLog']), '紀錄寫「等你確認」')
        hub_json('POST', '/api/forge/auto-run', {})
        check(len(forge_jobs()) == 1, '已經有一個在等的，不會再建第二個')
        hub_json('POST', f"/api/jobs/{js[0]['id']}/cancel")

        print('2. 每日上限內自動：上限內直接衝')
        hub_json('POST', '/api/settings', {'forgeAuto': {'mode': 'auto', 'everyMin': 30, 'dailyCap': 500000, 'rules': [RULE]}})
        hub_json('POST', '/api/forge/auto-run', {})
        js = [j for j in forge_jobs() if j['status'] != 'cancelled']
        check(len(js) == 1 and js[0]['status'] in ('approved', 'running', 'done') and len(js[0]['batches'][0]['gear']) == 1, f"上限 50 萬：只排 1 件（5 次）、直接開始（{[(j['status'], len(j['batches'][0]['gear'])) for j in js]}）")
        done = await wait(lambda: (lambda j: j if j['status'] in ('done', 'failed') else None)(next(x for x in forge_jobs() if x['id'] == js[0]['id'])), 60)
        check(done and done['status'] == 'done', '強化工作做完')
        f = hub_json('GET', '/api/forge')
        check(0 < f['spentToday'] <= 500000, f"今天已花 {f['spentToday']:,}")
        forged = {x['uid'] for r in f['log'] for x in r['results']}

        print('3. 超過上限：等確認；衝過的不再衝')
        # 剛衝完、角色還沒回報新的背包時不會建工作；回報後才建
        def again():
            hub_json('POST', '/api/forge/auto-run', {})
            return [j for j in forge_jobs() if j['id'] != js[0]['id'] and j['status'] != 'cancelled'] or None
        js2 = await wait(again, 40, 2) or []
        check(len(js2) == 1 and js2[0]['status'] == 'pending', f"上限用完了：建立工作等你確認（{[j['status'] for j in js2]}）")
        check(js2 and not ({x['uid'] for x in js2[0]['batches'][0]['gear']} & forged), '衝過的那件不會再排進去')
        hub_json('POST', f"/api/jobs/{js2[0]['id']}/cancel")

        print('4. 詛咒卷軸一律等確認')
        hub_json('POST', '/api/settings', {'forgeAuto': {'mode': 'auto', 'everyMin': 30, 'dailyCap': 100000000, 'rules': [{**RULE, 'item': 'i2040899'}]}})
        hub_json('POST', '/api/forge/auto-run', {})
        js3 = [j for j in forge_jobs() if j['status'] == 'pending']
        check(len(js3) == 1 and js3[0]['batches'][0]['forge']['cursed'] > 0, '詛咒卷軸：上限很高也是等你確認')
        hub_json('POST', f"/api/jobs/{js3[0]['id']}/cancel")

        print('5. 面板')
        ctx = await env.browser.new_context(viewport={'width': 1400, 'height': 900}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
        await d.goto(HUB + '/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab=forge]'); await d.wait_for_timeout(1500)
        txt = await d.inner_text('#faCard')
        check('工地手套' in txt and '詛咒' in txt and '今天已花' in txt, '自動強化卡片列出規則、今天花了多少')
        check(await d.eval_on_selector('#faMode', 'e => e.value') == 'auto', '模式顯示每日上限內自動')
        await d.click('[data-fadel="0"]'); await d.wait_for_timeout(800)
        check(not hub_json('GET', '/api/data')['settings']['forgeAuto']['rules'], '刪掉規則')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
