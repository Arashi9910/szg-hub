"""工作清單一鍵清除：已完成／已取消（含掛機指令）一次清掉，失敗的另外清，待確認的不動"""
import asyncio, json, sys, time
from harness import Env, hub_json, http, HUB

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)

async def main():
    async with Env() as env:
        await env.open_accounts(['A1']); await env.wait_chars(1)
        mk = lambda: hub_json('POST', '/api/jobs', {'kind': 'lock', 'fromCharId': 'c1', 'batches': [{'items': [], 'gear': [{'uid': 'nope', 'name': '不存在的'}]}]})['jobs'][0]
        a = mk(); hub_json('POST', f"/api/jobs/{a['id']}/approve")       # 會完成（找不到東西→略過完成）
        b = mk(); hub_json('POST', f"/api/jobs/{b['id']}/cancel")        # 已取消
        c = mk()                                                         # 待確認
        hub_json('POST', '/api/idle', {'targets': [{'charId': 'c1', 'action': 'stop'}]})  # 掛機指令
        end = time.time() + 30
        while time.time() < end and not all(j['status'] in ('done', 'cancelled', 'pending') for j in hub_json('GET', '/api/data')['jobs']): await asyncio.sleep(1)
        js = hub_json('GET', '/api/data')['jobs']
        print('   工作：', [(j['kind'], j['status']) for j in js])
        ctx = await env.browser.new_context(viewport={'width': 1400, 'height': 900}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
        d.on('dialog', lambda dl: asyncio.ensure_future(dl.accept()))
        await d.goto(HUB + '/'); await d.wait_for_timeout(1500)
        await d.click('#jobBtn'); await d.wait_for_timeout(500)
        btn = d.locator('#jobOutAll [data-jobs-clear="done"]')
        check(await btn.count() == 1, '工作清單有「🗑 清除已完成的」：' + (await btn.inner_text() if await btn.count() else ''))
        await btn.click(); await d.wait_for_timeout(1500)
        left = hub_json('GET', '/api/data')['jobs']
        check([j['id'] for j in left] == [c['id']], '已完成、已取消、掛機指令都清掉，只剩待確認的')
        check(await d.locator('#jobOutAll tbody tr').count() == 1, '清單畫面跟著更新')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
