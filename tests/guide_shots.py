"""產生公開版圖文教學的截圖（模擬遊戲資料，沒有任何個人資料）：SZG_REPO=公開版資料夾 python3 guide_shots.py 輸出資料夾"""
import asyncio, os, sys, json, time
os.environ['MOCK_APPEARANCE'] = '1'
os.environ['MOCK_MORE_ACCTS'] = '1'
os.environ['MOCK_PARTY'] = 'c3,c4'
os.environ['MOCK_BOSS_DPS'] = '300'
os.environ['MOCK_BOSS_RESPAWN_MS'] = '3600000'
from harness import Env, hub_json
OUT = sys.argv[1] if len(sys.argv) > 1 else '/tmp/shots'
HUB = 'http://127.0.0.1:8787'

async def main():
    async with Env() as env:
        hub_json('POST', '/api/settings', {'boss': {'mode': 'preview', 'charMobs': {'c3': ['*'], 'c1': ['mBoss1']}, 'estMax': 15, 'visitMax': 20},
                                           'parties': [{'id': 'p1', 'name': '隊伍 1', 'members': ['c3', 'c4'], 'map': 'gms104040000'}],
                                           'mainCharId': 'c1'})
        pages = await env.open_accounts(['A1', 'A2', 'A3', 'A4'])
        await env.wait_chars(4)
        await asyncio.sleep(25)   # 全身照、王的狀態、世界資料
        g = pages[0]
        await g.set_viewport_size({'width': 1100, 'height': 700}); await g.wait_for_timeout(800)
        await g.screenshot(path=f'{OUT}/02-game-connected.png')
        ctx = await env.browser.new_context(viewport={'width': 1400, 'height': 860}); env.contexts.append(ctx)
        d = await ctx.new_page()
        d.on('dialog', lambda dlg: asyncio.ensure_future(dlg.dismiss()))
        await d.goto(HUB + '/'); await d.wait_for_timeout(2500)
        async def tab(name, file, setup=None, wait=1500, full=False):
            await d.click(f'nav button[data-tab={name}]'); await d.wait_for_timeout(wait)
            if setup: await setup()
            await d.wait_for_timeout(500)
            await d.screenshot(path=f'{OUT}/{file}', full_page=full)
        await tab('overview', '03-overview.png')
        await d.click('#jobBtn'); await d.wait_for_timeout(800); await d.screenshot(path=f'{OUT}/04-jobs.png'); await d.click('#jobClose')
        await tab('gear', '05-gear.png')
        await tab('dex', '06-dex.png')
        await tab('trade', '07-trade.png')
        await tab('bag', '08-bag.png')
        async def fac():
            await d.click('#bdViewSeg [data-bview2=factory]')
        await tab('board', '09-board.png', fac, 2500)
        await tab('party', '10-party.png')
        async def boss():
            await d.click('#bossRun'); await d.wait_for_timeout(1500)
        await tab('maps', '11-maps-boss.png', boss, 2500)
        await tab('market', '12-market.png')
        await tab('quiz', '13-quiz.png')
        await tab('forge', '14-forge.png')
        await tab('guild', '15-guild.png')
        await d.click('nav button[data-tab=overview]'); await d.wait_for_timeout(800)
        await d.click('#mBox > summary'); await d.wait_for_timeout(800)
        await d.fill('#mBase', 'https://my-pc.tailxxxx.ts.net'); await d.fill('#mName', '我的手機'); await d.click('#mPair'); await d.wait_for_timeout(800)
        await d.screenshot(path=f'{OUT}/16-mobile-pair.png')
        tok = hub_json('POST', '/api/m/pair', {'name': '截圖'})['token']
        mctx = await env.browser.new_context(viewport={'width': 390, 'height': 800}, is_mobile=True, device_scale_factor=2, extra_http_headers={'X-Forwarded-For': '100.64.0.9'}); env.contexts.append(mctx)
        p = await mctx.new_page()
        await p.goto(HUB + f'/m#t={tok}'); await p.wait_for_timeout(2500)
        await p.fill('#tgt', '50'); await p.wait_for_timeout(400)
        await p.screenshot(path=f'{OUT}/17-mobile-chars.png')
        await p.click('nav [data-v=boss]'); await p.wait_for_timeout(2000)
        await p.screenshot(path=f'{OUT}/18-mobile-boss.png')
    print('ok')

asyncio.run(main())
