"""總覽：每小時楓幣、合計賺得（遊戲的本次掛機報告＋累計賺得）"""
import asyncio, sys
from harness import Env, hub_json, http, HUB, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    ok = ok and bool(cond)

async def main():
    async with Env() as env:
        # c3、c4 掛機中；c1 沒掛機（不算進每小時）；c2 沒有報告
        http('GET', MOCK + '/__mock/session?acct=A2&char=c3&money=100000&activeMs=7200000&earned=1000000')
        http('GET', MOCK + '/__mock/session?acct=A3&char=c4&money=30000&activeMs=10800000&earned=2000000')
        http('GET', MOCK + '/__mock/session?acct=A1&char=c1&money=40000&activeMs=3600000&earned=5000000')
        await env.open_accounts(['A1', 'A2', 'A3']); await env.wait_chars(3)
        await asyncio.sleep(4)
        chars = hub_json('GET', '/api/data')['chars']
        print('1. 腳本回報')
        s3 = chars.get('c3', {}).get('char', {})
        check(s3.get('session', {}).get('money') == 100000 and s3['session']['activeMs'] == 7200000 and s3.get('earned') == 1000000, f"回報本次掛機與累計：{s3.get('session')} earned={s3.get('earned')}")

        print('2. 總覽')
        ctx = await env.browser.new_context(viewport={'width': 1500, 'height': 950}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []
        d.on('pageerror', lambda e: errs.append(str(e)))
        await d.goto(HUB + '/'); await d.wait_for_timeout(2500)
        g = await d.inner_text('#ovSummary')
        check('楓幣收入' in g and '6 萬' in g, '每小時楓幣只算掛機中的（5 萬＋1 萬）：' + g.replace('\n', ' | '))
        check('合計賺得' in g and '17 萬' in g and '累計 800 萬' in g, '合計賺得 17 萬、累計 800 萬')
        hdr = await d.inner_text('#ovTable thead')
        check('每小時楓幣' in hdr, '表格有「每小時楓幣」欄')
        row = await d.inner_text('#ovTable tbody tr:has-text("弓箭分身")')
        check('5 萬' in row and '本次 10 萬' in row, '弓箭分身：每小時 5 萬、本次 10 萬：' + row.replace('\n', ' | ')[:200])
        await d.click('#ovTable th[data-ovsort=mrate]'); await d.wait_for_timeout(400)
        await d.click('#ovTable th[data-ovsort=mrate]'); await d.wait_for_timeout(400)
        first = await d.inner_text('#ovTable tbody tr >> nth=0')
        check('弓箭分身' in first, '可以依每小時楓幣排序（最多的在最上面）')
        check(not errs, '沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('全部通過' if ok else '有失敗')
    sys.exit(0 if ok else 1)

asyncio.run(main())
