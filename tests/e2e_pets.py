"""總覽小怪：兩隻有畫出來、會自己走、點了有反應、連點 5 下會倒下再復活、可以收起來"""
import asyncio, sys
from harness import Env, HUB

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    ok = ok and bool(cond)

async def main():
    async with Env() as env:
        ctx = await env.browser.new_context(viewport={'width': 1280, 'height': 800}); env.contexts.append(ctx)
        dash = await ctx.new_page(); errs = []
        dash.on('pageerror', lambda e: errs.append(str(e)))
        await dash.goto(HUB + '/'); await dash.wait_for_timeout(1500)
        print('1. 畫出來')
        pets = await dash.query_selector_all('#ovPets img.pet')
        check(len(pets) == 2, f'兩隻小怪（{len(pets)}）')
        names = [await p.get_attribute('alt') for p in pets]
        check(names == ['綠水靈', '菇菇寶貝'], '名字：' + '、'.join(names))
        await dash.screenshot(path='/tmp/pets1.png', clip={'x': 0, 'y': 0, 'width': 1280, 'height': 420})

        print('2. 自己會動')
        xs0 = await dash.eval_on_selector_all('#ovPets img.pet', 'a => a.map(e => e.style.left + e.getAttribute("src").length)')
        await dash.wait_for_timeout(6000)
        xs1 = await dash.eval_on_selector_all('#ovPets img.pet', 'a => a.map(e => e.style.left + e.getAttribute("src").length)')
        check(xs0 != xs1, '6 秒內位置或動作有變')

        print('3. 點擊反應')
        await dash.click('#ovPets img[data-pet="slime"]', force=True); await dash.wait_for_timeout(200)
        check(await dash.query_selector('#ovPets .pet-bub') is not None, '點一下有對話泡泡')
        await dash.wait_for_timeout(1600)
        for _ in range(5):
            await dash.click('#ovPets img[data-pet="mush"]', force=True); await dash.wait_for_timeout(120)
        act = await dash.evaluate('pets.find(p => p.k === "mush").act')
        check(act == 'die', f'連點 5 下倒下（{act}）')
        await dash.wait_for_timeout(500)
        await dash.screenshot(path='/tmp/pets2.png', clip={'x': 0, 'y': 0, 'width': 1280, 'height': 420})
        await dash.wait_for_timeout(3500)
        act = await dash.evaluate('pets.find(p => p.k === "mush").act')
        op = await dash.eval_on_selector('#ovPets img[data-pet="mush"]', 'e => e.style.opacity')
        check(act != 'die' and op == '1', f'幾秒後復活（{act}，opacity {op}）')

        print('4. 收起來')
        await dash.click('#ovPetsHide')
        check(not await dash.is_visible('#ovPets'), '按 × 收起')
        await dash.reload(); await dash.wait_for_timeout(1500)
        check(not await dash.is_visible('#ovPets') and await dash.is_visible('#ovPetsShow'), '重新整理後維持收起')
        await dash.click('#ovPetsShow')
        check(await dash.is_visible('#ovPets'), '按「放出小怪」恢復')
        check(not errs, '沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('全部通過' if ok else '有失敗'); sys.exit(0 if ok else 1)

asyncio.run(main())
