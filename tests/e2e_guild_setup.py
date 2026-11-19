"""公會倉庫設定介面：新手引導、快速套用、選角色（含 A/B 組）、浮動總和條件；自動存入只動勾選的角色"""
import asyncio, json, sys, time
from harness import Env, hub_json, http, HUB, MOCK
from e2e_guild import EXT, mock_state

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)

PHYS = {'sword', 'twoSword', 'axe', 'twoAxe', 'mace', 'twoMace', 'spear', 'polearm', 'bow', 'crossbow', 'claw', 'dagger', 'knuckle', 'gun'}
def judge(g):  # 跟面板 rollProfileDefault 同一套預設
    t = g.get('type'); st = ['incMAD'] if t in ('wand', 'staff') else ['incPAD'] if t in PHYS else ['incSTR', 'incDEX', 'incINT', 'incLUK']
    return sum(g['cleanStats'].get(k, 0) - g['baseStats'].get(k, 0) for k in st) >= 1
def dsum(g): return sum(g['cleanStats'].get(k, 0) - g['baseStats'].get(k, 0) for k in set(g['cleanStats']) | set(g['baseStats']))

async def main():
    async with Env(extdb=EXT) as env:
        pages = await env.open_accounts(['A1', 'A2', 'A3'])
        for pg in pages:
            await pg.evaluate("fetch('/api/game', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ type: 'stop', requestId: crypto.randomUUID(), characterId: sessionStorage.getItem('mapleCharacter') }) })")
        await env.wait_chars(3); await asyncio.sleep(4)
        ctx = await env.browser.new_context(viewport={'width': 1400, 'height': 900}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []
        d.on('pageerror', lambda e: errs.append(str(e)))
        d.on('dialog', lambda dl: asyncio.ensure_future(dl.accept()))
        await d.goto(HUB + '/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab=guild]'); await d.wait_for_timeout(1500)
        await d.click('#gRulesOpen'); await d.wait_for_timeout(600)

        print('1. 新手引導')
        check(await d.eval_on_selector('#gGuideBox', 'e => e.open'), '還沒設定時引導是展開的')
        check('0/4' in await d.inner_text('#gSetupState'), '顯示已完成 0/4 步')
        check('還沒設定要存什麼' in await d.inner_text('#gdSummary'), '規則摘要提示還沒設定')

        print('2. 快速套用「卷軸＋比標準好的裝備」')
        await d.click('[data-gdpreset="good"]'); await d.wait_for_timeout(1200)
        dep = hub_json('GET', '/api/data')['settings']['guildDep']
        check(set(dep['cats']) == {'卷軸', '裝備'} and dep['conds'] == [{'k': '_pass', 'min': ''}], f'存檔：{dep}')
        summ = await d.inner_text('#gdSummary')
        check('所有卷軸' in summ and '依部位基準達標' in summ and '全部角色' in summ, '摘要：' + summ.replace('\n', ' / '))
        check(await d.is_checked('[data-gdcat="卷軸"]') and await d.is_checked('[data-gdcat="裝備"]'), '整類勾選同步打勾')
        st = mock_state()
        want = sum(1 for a in st['accounts'].values() for g in a['chars'][a['active']]['equipmentBag'] if not g['locked'] and judge(g))
        prev = await d.inner_text('#gdPreview')
        check(f'符合 {want} 件' in prev, f'預覽符合件數＝依部位基準達標的件數（{want}）：' + prev.split('\n')[0])

        print('3. 選角色')
        check('全部角色' in await d.inner_text('#gdChars') and await d.locator('[data-gdchar]').count() == 0, '全部角色時收起來，不列出一長串勾選框')
        await d.click('#gdCharsCustom'); await d.wait_for_timeout(300)
        check('A 組' in await d.inner_text('#gdChars'), '按「自訂角色」後依 A／B 組列出')
        await d.click('[data-gdchar="c3"]'); await d.wait_for_timeout(1200)
        dep = hub_json('GET', '/api/data')['settings']['guildDep']
        check(dep['chars'] is not None and 'c3' not in dep['chars'] and 'c1' in dep['chars'], f"取消弓箭分身後存檔 chars={dep['chars']}")
        await d.click('[data-gdchar="c3"]'); await d.wait_for_timeout(1200)
        check(hub_json('GET', '/api/data')['settings']['guildDep']['chars'] is None, '全部勾回來＝全部角色（包含之後新增的）')
        await d.click('[data-gdgroup="B"]'); await d.wait_for_timeout(1200)
        dep = hub_json('GET', '/api/data')['settings']['guildDep']
        check(dep['chars'] == [], f"只選 B 組：這三個帳號都只有一隻，B 組是空的 → {dep['chars']}")
        await d.click('[data-gdgroup="A"]'); await d.wait_for_timeout(300)
        await d.click('[data-gdchar="c3"]'); await d.wait_for_timeout(1200)

        print('4. 自動存入只動勾選的角色')
        hub_json('POST', '/api/settings', {'guildAuto': {'mode': 'preview', 'everyMin': 30}})
        r = hub_json('POST', '/api/guild/auto-run', {})
        msg = (r['log'] or [{}])[-1].get('msg', '')
        check('試跑' in msg and '弓箭分身' not in msg and ('本尊劍士' in msg or '倉庫分身' in msg), '試跑紀錄：' + msg[:120])
        await d.reload(); await d.wait_for_timeout(2000); await d.click('nav button[data-tab=guild]'); await d.wait_for_timeout(1500)
        await d.click('#gRulesOpen'); await d.wait_for_timeout(600)
        if not await d.locator('[data-gdchar="c1"]').count(): await d.click('#gdCharsCustom'); await d.wait_for_timeout(300)
        check(await d.is_checked('[data-gdchar="c1"]') and not await d.is_checked('[data-gdchar="c3"]'), '重新整理後角色選擇保留')
        check('1/4' in await d.inner_text('#gSetupState') or '2/4' in await d.inner_text('#gSetupState'), '引導進度更新：' + await d.inner_text('#gSetupState'))
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
