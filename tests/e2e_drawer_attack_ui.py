"""角色抽屜「掛機設定」的攻擊技能（技能 1／2／3，遊戲 openAttackSlot 的版面）＋副本分頁打開角色抽屜。
只驗面板送出的 /api/idle cfg 指令格式 {type:'attackSlot', slot, skill, targets, map, continuous(只有技能 1)}；遊戲端套用由 attackSlot 指令那邊的測試驗"""
import asyncio, json, sys, time
from harness import Env, hub_json, HUB

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)
def hub_ic(c): return ((hub_json('GET', '/api/data')['chars'].get(c) or {}).get('char') or {}).get('idleCfg')
async def wait(fn, sec=30, step=1):
    end = time.time() + sec
    while time.time() < end:
        try: v = fn()
        except Exception: v = None
        if v: return v
        await asyncio.sleep(step)
    return None

async def main():
    async with Env() as env:
        await env.open_accounts(['A1', 'A2'])
        await env.wait_chars(2)
        await wait(lambda: hub_ic('c1') and hub_ic('c3'), 40)
        hub_json('POST', '/api/settings', {'raid': {'kind': 'papulatus', 'leader': 'c1', 'members': ['c3']}})
        check(await wait(lambda: len(hub_json('GET', '/api/world').get('maps') or []) > 0, 40), '中控有地圖資料（怪物清單從 /api/world 的 maps[].mobIds 來）')

        ctx = await env.browser.new_context(viewport={'width': 1500, 'height': 1000}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
        msgs = []; d.on('dialog', lambda dl: (msgs.append(dl.message), asyncio.ensure_future(dl.accept())))
        sent = []
        def on_req(r):
            if r.method == 'POST' and r.url.endswith('/api/idle'):
                try: sent.append(json.loads(r.post_data or '{}'))
                except Exception: pass
        d.on('request', on_req)
        await d.goto(HUB + '/'); await d.wait_for_timeout(1500)
        await d.click('nav button[data-tab=raid]'); await d.wait_for_timeout(3000)

        print('1. 副本分頁：戰前檢查的「設定」按鈕打開角色抽屜（不影響整列勾選）')
        await d.wait_for_selector('#rdPrep tr[data-rpsel="c1"]', timeout=15000)
        check(await d.locator('#rdPrep tr[data-rpsel="c1"] button[data-rdcd="c1"]').count() == 1, '戰前檢查 c1 那列有「設定」按鈕')
        await d.click('#rdPrep tr[data-rpsel="c1"] button[data-rdcd="c1"]'); await d.wait_for_timeout(800)
        check(await d.locator('#charDrawer').count() == 1 and '本尊劍士' in await d.inner_text('#charDrawer h3'), '抽屜打開，是本尊劍士')
        check('on' in (await d.get_attribute('#charDrawer [data-cdtab="idle"]', 'class') or ''), '直接到「掛機設定」分頁')
        check('on' not in (await d.get_attribute('#rdPrep tr[data-rpsel="c1"]', 'class') or '').split(), '按「設定」不會勾選那一列')
        txt = await d.inner_text('#cdAtk')
        check('攻擊技能' in txt and '技能 1' in txt and '技能 2' in txt and '技能 3' in txt, '掛機設定有技能 1／2／3 三格')
        check('強力攻擊' in await d.inner_text('#cdAtk [data-cdatk="0"]') and '無' in await d.inner_text('#cdAtk [data-cdatk="1"]'), f'技能 1＝主動技能 強力攻擊、技能 2＝無（{txt!r}）')
        await d.click('#charDrawer [data-cdclose]'); await d.wait_for_timeout(400)
        await d.click('#rdPrep tr[data-rpsel="c1"] [data-rdcd="c1"].rd-cdlink'); await d.wait_for_timeout(800)
        check(await d.locator('#cdAtk').count() == 1, '點戰前檢查「攻擊格」的文字也能打開抽屜')
        check('on' not in (await d.get_attribute('#rdPrep tr[data-rpsel="c1"]', 'class') or '').split(), '點攻擊格文字不會勾選那一列')

        print('2. 技能 2：選技能＋指定怪物，每秒重畫不會洗掉草稿')
        await d.click('#cdAtk [data-cdatk="1"]'); await d.wait_for_timeout(400)
        opts = await d.locator('[data-cdatksk="1"] option').all_inner_texts()
        check(opts[:1] == ['無'] and '普通攻擊' in opts and '強力攻擊' in opts and '鐵壁' not in opts, f'技能 2 下拉：無＋普通攻擊＋學會的攻擊技能（{opts}）')
        await d.select_option('[data-cdatksk="1"]', 's1001004'); await d.wait_for_timeout(300)
        rows = await d.locator('#cdAtk [data-cdatkmob]').all_inner_texts()
        check(len(rows) == 1 and '紅寶' in rows[0], f'列出目前地圖（射手訓練場）的怪物（{rows}）')
        await d.click('#cdAtk [data-cdatkmob="m1210101"] div'); await d.wait_for_timeout(300)  # 點整列（名字）就能勾
        check(await d.locator('#cdAtk [data-cdatkmob="m1210101"] input').is_checked(), '點整列勾選怪物')
        await d.evaluate('poll()'); await d.wait_for_timeout(3000)
        check(await d.locator('[data-cdatksk="1"]').input_value() == 's1001004' and await d.locator('#cdAtk [data-cdatkmob="m1210101"] input').is_checked(), '重畫後草稿還在（技能、勾的怪物）')
        check('只適用這張地圖' in await d.inner_text('#cdAtk'), '說明：指定怪物只適用這張地圖')
        n0 = len(sent)
        await d.click('[data-cdatksave="1"]'); await d.wait_for_timeout(1200)
        t = ((sent[n0] if len(sent) > n0 else {}).get('targets') or [{}])[0]
        check(t.get('charId') == 'c1' and t.get('action') == 'cfg', f'送 /api/idle cfg 給 c1（{t}）')
        check(t.get('cmd') == {'type': 'attackSlot', 'slot': 1, 'skill': 's1001004', 'targets': ['m1210101'], 'map': 'gms104040000'}, f'技能 2 指令格式（{t.get("cmd")}）')
        check('技能2 改成 強力攻擊' in (t.get('label') or ''), f'工作名稱（{t.get("label")}）')

        print('3. 技能 1：沒有「無」、有持續施放')
        await d.click('#cdAtk [data-cdatk="0"]'); await d.wait_for_timeout(400)
        opts = await d.locator('[data-cdatksk="0"] option').all_inner_texts()
        check('無' not in opts and '普通攻擊' in opts and await d.locator('[data-cdatksk="0"]').input_value() == 's1001004', f'技能 1 下拉沒有「無」，目前是強力攻擊（{opts}）')
        await d.select_option('[data-cdatksk="0"]', 'basic'); await d.wait_for_timeout(200)
        await d.check('[data-cdatkcont]'); await d.wait_for_timeout(200)
        n0 = len(sent)
        await d.click('[data-cdatksave="0"]'); await d.wait_for_timeout(1200)
        t = ((sent[n0] if len(sent) > n0 else {}).get('targets') or [{}])[0]
        check(t.get('cmd') == {'type': 'attackSlot', 'slot': 0, 'skill': 'basic', 'targets': [], 'map': 'gms104040000', 'continuous': True}, f'技能 1 指令格式（{t.get("cmd")}）')
        check('技能1 改成 普通攻擊' in (t.get('label') or ''), f'工作名稱（{t.get("label")}）')

        print('4. 技能 3 改成「無」')
        await d.click('#cdAtk [data-cdatk="2"]'); await d.wait_for_timeout(400)
        check(await d.locator('[data-cdatksk="2"]').input_value() == '' and await d.locator('#cdAtk [data-cdatkmob]').count() == 0, '技能 3＝無，不列怪物')
        n0 = len(sent)
        await d.click('[data-cdatksave="2"]'); await d.wait_for_timeout(1200)
        t = ((sent[n0] if len(sent) > n0 else {}).get('targets') or [{}])[0]
        check(t.get('cmd') == {'type': 'attackSlot', 'slot': 2, 'skill': None, 'targets': [], 'map': 'gms104040000'}, f'技能 3 指令格式（{t.get("cmd")}）')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
