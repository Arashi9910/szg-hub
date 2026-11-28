"""公倉存入「個別挑選」：自動喝水在用的藥水（藍色藥水＝mock 的 mpItem）也要列出來（v0.82.2 回報：藍色藥水看不到）；
整類勾選「消耗」不會存喝水用的；個別勾了才存，而且每隻至少留 supplyKeep 個。"""
import asyncio, json, sys, time
from harness import Env, hub_json, http, HUB, MOCK

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)
def mock_state(): return json.loads(http('GET', MOCK + '/__mock/state')[1])
def blue():
    st = mock_state(); return {a['active']: a['chars'][a['active']]['inventory'].get('i2000003', 0) for a in st['accounts'].values()}
async def wait(fn, sec=40, step=1):
    end = time.time() + sec
    while time.time() < end:
        try:
            v = fn()
            if v: return v
        except Exception: pass
        await asyncio.sleep(step)
    return None

async def main():
    async with Env() as env:
        pages = await env.open_accounts(['A1', 'A2'])
        for pg in pages:  # 掛機會喝水，測試期間先暫停
            await pg.evaluate("fetch('/api/game', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ type: 'stop', requestId: crypto.randomUUID(), characterId: sessionStorage.getItem('mapleCharacter') }) })")
        await env.wait_chars(2); await asyncio.sleep(11)
        d = hub_json('GET', '/api/data')['chars']
        sup = [s['char']['name'] for s in d.values() if any(it['key'] == 'i2000003' and it.get('supply') for it in s.get('items') or [])]
        check(sup, f'有角色的藍色藥水是喝水用（{sup}）')

        print('1. 面板：個別挑選列出藍色藥水＋「喝水用」；勾整類「消耗」後還能個別勾')
        hub_json('POST', '/api/settings', {'guildDep': {'names': [], 'cats': ['消耗'], 'conds': [], 'keep': 0, 'supplyKeep': 150}, 'guildAuto': {'mode': 'off', 'everyMin': 30}})
        ctx = await env.browser.new_context(viewport={'width': 1500, 'height': 1000}); env.contexts.append(ctx)
        p = await ctx.new_page(); errs = []; p.on('pageerror', lambda e: errs.append(str(e)))
        await p.goto(HUB + '/'); await p.wait_for_timeout(1500)
        await p.click('nav button[data-tab=guild]'); await p.wait_for_timeout(2500)
        await p.click('#gRulesOpen'); await p.wait_for_timeout(800)
        await p.click('#gdPickBox summary'); await p.wait_for_timeout(1000)
        row = p.locator('#gdList tr', has_text='藍色藥水')
        check(await row.count() == 1, '個別挑選有藍色藥水')
        txt = await row.inner_text() if await row.count() else ''
        check('喝水用' in txt, f'標示喝水用（{txt!r}）')
        cb = row.locator('input[data-gdpick]')
        check(await cb.count() == 1 and not await cb.is_disabled() and not await cb.is_checked(), '勾了整類「消耗」，藍色藥水還是沒勾、可以個別勾')
        check(await p.locator('#gdSupKeep').input_value() == '150', '喝水用藥水保留欄＝150')
        check(not errs, f'沒有 JS 錯誤（{errs[:2]}）')

        print('2. 整類「消耗」自動存入：不存喝水用的藍色藥水')
        b0 = blue()
        hub_json('POST', '/api/guild/refresh', {}); await asyncio.sleep(6)
        hub_json('POST', '/api/settings', {'guildAuto': {'mode': 'deposit', 'everyMin': 30}})
        hub_json('POST', '/api/guild/auto-run', {}); await asyncio.sleep(15)
        check(blue() == b0, f'藍色藥水沒被存（{b0} → {blue()}）')

        print('3. 個別勾藍色藥水：每隻留 150 個，多的才存')
        hub_json('POST', '/api/settings', {'guildDep': {'names': ['i:i2000003'], 'cats': [], 'conds': [], 'keep': 0, 'supplyKeep': 150}})
        hub_json('POST', '/api/guild/auto-run', {})
        want = {k: min(v, 150) for k, v in b0.items()}
        got = await wait(lambda: (lambda b: b if b == want else None)(blue()), 60)
        check(got == want, f'每隻剩 min(原本,150)（{b0} → {blue()}，要 {want}）')
        if got != want: print('   公倉紀錄：', [l['msg'][:160] for l in (hub_json('GET', '/api/guild').get('log') or [])[-4:]])
        hub_json('POST', '/api/settings', {'guildAuto': {'mode': 'off', 'everyMin': 30}})
    print('\n全部通過' if ok else '\n有失敗'); sys.exit(0 if ok else 1)

asyncio.run(main())
