"""技能書獨立一類（v0.63）：背包類別、公倉分頁、存入規則（整類、快速套用、個別挑選的類別）、自動存入、派工自動販售範本"""
import asyncio, json, sys, time
from harness import Env, hub_json, http, HUB, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    ok = ok and bool(cond)

async def until(fn, sec, step=1):
    end = time.time() + sec
    while time.time() < end:
        try:
            v = fn()
            if v: return v
        except Exception: pass
        await asyncio.sleep(step)
    return None

def mock_state(): return json.loads(http('GET', MOCK + '/__mock/state')[1])

async def main():
    async with Env() as env:
        await env.open_accounts(['A1'])
        d = await env.wait_chars(1)
        it = next((i for i in d['chars']['c1']['items'] if i['key'] == 'i2290001'), None)
        check(it and it['kind'] == '技能書', f"腳本把技能書回報成「技能書」類（{it and it['kind']}）")
        ctx = await env.browser.new_context(viewport={'width': 1500, 'height': 950}); env.contexts.append(ctx)
        p = await ctx.new_page(); errs = []
        p.on('pageerror', lambda e: errs.append(str(e)))
        p.on('dialog', lambda dl: asyncio.ensure_future(dl.accept()))
        await p.goto(HUB + '/'); await p.wait_for_timeout(2500)

        print('1. 背包')
        await p.click('nav button[data-tab=bag]'); await p.wait_for_timeout(500)
        import re
        kinds = [re.sub(r'\d+', '', x).strip() for x in (await p.inner_text('#bKinds')).split('\n') if x.strip()]
        check('技能書' in kinds and kinds.index('技能書') == kinds.index('消耗') + 1, f'背包類別有「技能書」，排在消耗後面：{kinds}')
        await p.click('[data-bkind="技能書"]'); await p.wait_for_timeout(400)
        await p.click('[data-bview="list"]'); await p.wait_for_timeout(400)
        txt = await p.inner_text('#bagOut')
        check('技能書：測試四轉技能' in txt and '紅色藥水' not in txt, '點「技能書」只列技能書')
        await p.click('[data-bkind="消耗"]'); await p.wait_for_timeout(400)
        check('技能書：測試四轉技能' not in await p.inner_text('#bagOut'), '「消耗」裡不再有技能書')

        print('2. 公倉：存入規則、自動存入、分頁')
        await p.click('nav button[data-tab=guild]'); await p.wait_for_timeout(500)
        await p.click('#gwRefresh'); await p.wait_for_timeout(5000)
        await p.click('#gRulesOpen'); await p.wait_for_timeout(500)
        cats = await p.inner_text('#gdCats')
        check('技能書' in cats, f'「整類存入」有技能書（{cats.strip()[:60]}）')
        await p.click('[data-gdpreset="scroll"]'); await p.wait_for_timeout(300)
        await p.click('[data-gdpreset="addbook"]'); await p.wait_for_timeout(1500)
        dep = hub_json('GET', '/api/data')['settings'].get('guildDep', {})
        check(set(dep.get('cats', [])) == {'卷軸', '技能書'}, f"快速套用「＋ 技能書」：卷軸＋技能書（{dep.get('cats')}）")
        await p.click('#gdPickBox summary'); await p.wait_for_timeout(300)
        await p.click('[data-gdkind="技能書"]'); await p.wait_for_timeout(400)
        lst = await p.inner_text('#gdList')
        check('技能書：測試四轉技能' in lst and '紅色藥水' not in lst, '個別挑選可以只看技能書')
        hub_json('POST', '/api/settings', {'guildAuto': {'mode': 'deposit', 'everyMin': 10}})
        hub_json('POST', '/api/guild/auto-run', {})
        ok_ = await until(lambda: mock_state()['guild']['items'].get('i2290001') == 3, 60, 2)
        check(ok_, f"自動存入照規則把技能書存進公倉（公倉 {mock_state()['guild']['items']}）")
        hub_json('POST', '/api/settings', {'guildAuto': {'mode': 'off', 'everyMin': 10}})
        await p.keyboard.press('Escape')
        await p.click('#gwRefresh'); await p.wait_for_timeout(5000)
        tabs = [await b.get_attribute('data-gwtab') for b in await p.locator('#gwTabs button').all()]
        check(tabs == ['gear', 'scroll', 'use', 'book', 'etc'], f'公倉分頁：裝備、卷軸、消耗、技能書、其他（{tabs}）')
        await p.click('#gwTabs [data-gwtab="book"]'); await p.wait_for_timeout(500)
        check('技能書：測試四轉技能' in await p.inner_text('#gwOut'), '公倉「技能書」分頁列出技能書')
        await p.click('#gwTabs [data-gwtab="use"]'); await p.wait_for_timeout(400)
        check('技能書：測試四轉技能' not in await p.inner_text('#gwOut'), '公倉「消耗」分頁沒有技能書')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('全部通過' if ok else '有失敗')
    sys.exit(0 if ok else 1)

asyncio.run(main())
