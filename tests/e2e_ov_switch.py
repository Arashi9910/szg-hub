"""總覽切換：勾到已經有分頁的角色不會白送；一鍵整組切換；同帳號兩隻都勾切到另一隻"""
import asyncio, json, sys, time
from harness import Env, hub_json, http, HUB, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)
def active(): return json.loads(http('GET', MOCK + '/__mock/state')[1])['accounts']['A1']['active']

async def wait_active(cid, sec=40):
    end = time.time() + sec
    while time.time() < end:
        s = hub_json('GET', '/api/data')['chars'].get(cid)
        if active() == cid and s and s.get('activeCharId') == cid and time.time() * 1000 - s['receivedAt'] < 5000: return True
        await asyncio.sleep(1)
    return False

async def main():
    async with Env() as env:
        await env.open_accounts(['A1']); await env.wait_chars(1)
        ctx = await env.browser.new_context(viewport={'width': 1500, 'height': 900}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
        d.on('dialog', lambda dl: asyncio.ensure_future(dl.accept()))
        await d.goto(HUB + '/'); await d.wait_for_timeout(2000)

        print('1. 勾到已經有分頁的')
        await d.check('[data-isel="c1"]'); await d.wait_for_timeout(300)
        n0 = len(hub_json('GET', '/api/data')['jobs'])
        await d.click('[data-idle="switch"]'); await d.wait_for_timeout(800)
        check('都已經有自己的遊戲分頁' in await d.inner_text('#idleMsg') and len(hub_json('GET', '/api/data')['jobs']) == n0, '提示「都已經有自己的遊戲分頁」，沒有送出指令')
        await d.click('#idleSelNone'); await d.wait_for_timeout(300)

        print('2. 一鍵切到 B 組')
        btn = d.locator('[data-ovgswitch="B"]')
        check(await btn.count() == 1, '總覽有「⇄ 全部切到 B 組」：' + (await btn.inner_text() if await btn.count() else ''))
        await btn.click(); await d.wait_for_timeout(500)
        check(await wait_active('c2'), '本尊小號切成目前角色')

        print('3. 同帳號兩隻都勾 → 切到沒有分頁的那隻')
        await d.reload(); await d.wait_for_timeout(2000)
        await d.check('[data-isel="c1"]'); await d.check('[data-isel="c2"]'); await d.wait_for_timeout(300)
        await d.click('[data-idle="switch"]'); await d.wait_for_timeout(800)
        msg = await d.inner_text('#idleMsg')
        check('已送出切換' in msg and '本來就有分頁' in msg, '提示：' + msg)
        check(await wait_active('c1'), '切回本尊劍士')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
