"""死掉自動原地復活：死亡 → 自動復活並重新開始掛機；超過每小時上限就停下來、總覽「需要處理」列出來；關掉就不復活"""
import asyncio, json, sys, time
from harness import Env, hub_json, http, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    ok = ok and bool(cond)

def mock_char(acct, cid):
    return json.loads(http('GET', MOCK + '/__mock/state')[1])['accounts'][acct]['chars'][cid]

async def wait(fn, sec, step=1):
    end = time.time() + sec
    while time.time() < end:
        v = fn()
        if v: return v
        await asyncio.sleep(step)
    return None

async def main():
    async with Env() as env:
        hub_json('POST', '/api/settings', {'idlePolicy': {'autoRenew': False, 'autoRevive': True, 'reviveMaxPerHour': 1}})
        await env.open_accounts(['A2'])
        await env.wait_chars(1)
        print('1. 死亡 → 自動原地復活並重新開始掛機')
        http('GET', MOCK + '/__mock/die?acct=A2&char=c3')
        c = await wait(lambda: (lambda c: c if c['hp'] > 0 else None)(mock_char('A2', 'c3')), 70)
        check(c and c.get('revives') == 1, '已復活（hp 恢復）')
        check(c and c['auto'], '重新開始掛機')
        log = hub_json('GET', '/api/data')['idleLog']
        check(any(l.get('kind') == 'revive' and '自動原地復活' in l['msg'] for l in log), '自動處理紀錄有寫')
        print('2. 超過每小時上限（設 1 次）→ 不再復活，「需要處理」列出來')
        await asyncio.sleep(2)
        http('GET', MOCK + '/__mock/die?acct=A2&char=c3')
        lim = await wait(lambda: next((l for l in hub_json('GET', '/api/data')['idleLog'] if l.get('kind') == 'reviveLimit'), None), 100)
        check(lim, '紀錄：' + (lim['msg'] if lim else '（沒有）'))
        check(mock_char('A2', 'c3')['hp'] == 0, '角色維持死亡，沒有再復活')
        ctx = await env.browser.new_context(viewport={'width': 1300, 'height': 800}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []
        d.on('pageerror', lambda e: errs.append(str(e)))
        await d.goto('http://127.0.0.1:8787/'); await d.wait_for_timeout(2500)
        txt = await d.inner_text('#ovAttn')
        check('死太多次' in txt, '總覽「需要處理」：' + txt.replace('\n', ' ')[:60])
        await d.click('#idleCard summary'); await d.wait_for_timeout(300)
        check(await d.is_checked('#ipRevive') and await d.input_value('#ipReviveMax') == '1', '設定畫面顯示開啟、上限 1')
        print('3. 關掉 → 不復活')
        await d.click('#ipRevive'); await d.wait_for_timeout(800)
        check(hub_json('GET', '/api/idle-policy')['policy']['autoRevive'] is False, '已關閉')
        hub_json('POST', '/api/settings', {'idlePolicy': {'autoRenew': False, 'autoRevive': False, 'reviveMaxPerHour': 60}})
        await asyncio.sleep(50)
        check(mock_char('A2', 'c3')['hp'] == 0, '關掉後角色沒有被復活')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    if not ok: print('\n'.join(env.logs[-20:]))
    print('全部通過' if ok else '有失敗'); sys.exit(0 if ok else 1)

asyncio.run(main())
