"""裝備、交易分頁的 A／B 組檢視：只顯示那一組角色的格子"""
import asyncio, json, sys, time
from harness import Env, hub_json, http, HUB, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)

async def main():
    async with Env() as env:
        await env.open_accounts(['A1', 'A2'])
        await env.wait_chars(2)
        hub_json('POST', '/api/settings', {'mainCharId': 'c3'})
        # 讓 B 組的本尊小號也有資料：切過去再等它回報
        hub_json('POST', '/api/idle', {'targets': [{'charId': 'c2', 'action': 'switch'}]})
        end = time.time() + 40
        while time.time() < end and not hub_json('GET', '/api/data')['chars'].get('c2'): await asyncio.sleep(1)
        check(bool(hub_json('GET', '/api/data')['chars'].get('c2')), '本尊小號（B 組）有資料了')
        ctx = await env.browser.new_context(viewport={'width': 1500, 'height': 1000}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
        await d.goto(HUB + '/'); await d.wait_for_timeout(1500)

        print('1. 裝備分頁')
        await d.click('nav button[data-tab=gear]'); await d.wait_for_timeout(1200)
        await d.click('#gear .vgBox [data-vg="A"]'); await d.wait_for_timeout(800)
        t = await d.inner_text('#gearOut')
        check('本尊劍士' in t and '弓箭分身' in t and '本尊小號' not in t, 'A 組：只有本尊劍士、弓箭分身的裝備')
        await d.click('#gear .vgBox [data-vg="B"]'); await d.wait_for_timeout(800)
        t = await d.inner_text('#gearOut')
        check('本尊小號' in t and '本尊劍士' not in t and '弓箭分身' not in t, 'B 組：只有本尊小號的裝備')
        await d.click('#gViewSeg [data-gv="matrix"]'); await d.wait_for_timeout(800)
        t = await d.inner_text('#gearOut')
        check('本尊小號' in t and '弓箭分身' not in t, '穿戴對照也只列 B 組')
        await d.click('#gear .vgBox [data-vg="all"]'); await d.wait_for_timeout(800)
        t = await d.inner_text('#gearOut')
        check('本尊小號' in t and '弓箭分身' in t and '本尊劍士' in t, '「全部」三隻都顯示')

        print('2. 交易分頁（本尊＝弓箭分身）')
        await d.click('nav button[data-tab=trade]'); await d.wait_for_timeout(1000)
        await d.click('#trade .vgBox [data-vg="A"]'); await d.wait_for_timeout(800)
        t = await d.inner_text('#collectPick')
        check('本尊劍士' in t and '本尊小號' not in t, 'A 組：收集清單只有本尊劍士')
        await d.click('#trade .vgBox [data-vg="B"]'); await d.wait_for_timeout(800)
        t = await d.inner_text('#collectPick')
        check('本尊小號' in t and '本尊劍士' not in t, 'B 組：收集清單只有本尊小號')
        check(await d.locator('#gear .vgBox [data-vg="B"].on').count() == 1, '兩個分頁共用同一個組別設定')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
