"""十字獵人分頁（面板）。/api/cross* 由伺服器那邊的子任務做；這裡用 playwright route 攔下來回假資料，只驗面板照契約送出的請求：
GET /api/cross → {quests, chars, cfg, log}；POST /api/cross/cfg（部分欄位）；POST /api/cross/accept {ids, quests?}；POST /api/cross/claim {ids}"""
import asyncio, copy, json, re, sys, time
from harness import Env, hub_json, HUB

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok = ok and bool(cond)

def mk_quests():
    qs, i = [], 0
    for lv in (20, 30, 40):
        for k in range(3):
            i += 1
            qs.append({'id': f'q{i}', 'name': f'十字獵人 {i}', 'level': lv, 'mob': f'm{i}', 'mobName': f'怪物{i}', 'count': 9999,
                       'maps': [{'id': f'map{i}a', 'name': f'地圖{i}A', 'noboss': True}, {'id': f'map{i}b', 'name': f'地圖{i}B', 'noboss': False}],
                       'defaultMap': f'map{i}a'})
    return qs

STATE = {
    'quests': mk_quests(),
    'chars': [
        {'id': 'c1', 'name': '本尊劍士', 'lv': 45, 'map': 'map1a', 'mapName': '地圖1A', 'coins': 2, 'exchanged': 0,
         'quests': {'q1': {'count': 9999, 'claimed': True}, 'q2': {'count': 1234, 'claimed': False}, 'q3': {'count': 9999, 'claimed': False}},
         'target': {'quest': 'q2', 'map': 'map2a'}, 'state': 'hunting', 'why': ''},
        {'id': 'c3', 'name': '弓箭分身', 'lv': 32, 'map': 'gms104040000', 'mapName': '射手訓練場', 'coins': 0, 'exchanged': 0,
         'quests': {}, 'target': None, 'state': 'blocked', 'why': '正在打王'},
    ],
    'cfg': {'enabled': False, 'ids': ['c1'], 'order': 'low', 'mapPref': {}, 'skip': []},
    'log': [{'at': int(time.time() * 1000) - 60000, 'charId': 'c1', 'name': '本尊劍士', 'msg': '接取 十字獵人 2'}],
}

async def main():
    async with Env() as env:
        await env.open_accounts(['A1', 'A2'])
        await env.wait_chars(2)
        ctx = await env.browser.new_context(viewport={'width': 1500, 'height': 1000}); env.contexts.append(ctx)
        d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
        dialogs = []; d.on('dialog', lambda dl: (dialogs.append(dl.message), asyncio.ensure_future(dl.accept())))
        posts = []; st = copy.deepcopy(STATE)

        async def route(r):
            req = r.request; path = re.sub(r'\?.*$', '', req.url.split(HUB, 1)[-1])
            body = {}
            if req.method == 'POST':
                try: body = json.loads(req.post_data or '{}')
                except Exception: body = {}
                posts.append((path, body))
            if path == '/api/cross' and req.method == 'GET': res = st
            elif path == '/api/cross/cfg': st['cfg'] = {**st['cfg'], **body}; res = {'ok': True, 'cfg': st['cfg']}
            elif path == '/api/cross/accept': res = {'jobs': ['j1', 'j2'], 'n': 2}
            elif path == '/api/cross/claim': res = {'jobs': ['j3'], 'n': 1}
            else: return await r.fulfill(status=404, body='{}', content_type='application/json')
            await r.fulfill(status=200, body=json.dumps(res, ensure_ascii=False), content_type='application/json')
        await d.route(re.compile(r'/api/cross(/|\?|$)'), route)
        last = lambda p: next((b for (x, b) in reversed(posts) if x == p), None)

        await d.goto(HUB + '/'); await d.wait_for_timeout(1500)
        print('1. 分頁存在、畫出狀態列／角色／任務總表／紀錄')
        check(await d.locator('nav button[data-tab=cross]').count() == 1 and '十字獵人' in await d.inner_text('nav button[data-tab=cross]'), 'nav 有「十字獵人」')
        await d.click('nav button[data-tab=cross]')
        await d.wait_for_selector('#crChars tr[data-crsel="c1"]', timeout=10000)
        txt = await d.inner_text('#cross')
        check('接受後才開始計算' in txt and '離線與參戰隊友擊殺也計入' in txt and '中控不自動兌換' in txt, '說明一行')
        check(await d.locator('#crEnabled').count() == 1 and await d.locator('[data-crorder=low].on').count() == 1, '自動狩獵開關、順序（等級低的先＝目前）')
        c1 = await d.inner_text('#crChars tr[data-crsel="c1"]')
        check('打獵中' in c1 and '十字獵人 2' in c1 and '1,234 / 9,999' in c1, f'c1 打獵中＋進度條（{c1!r}）')
        check('2／6／1' in c1 and '1 張可領' in c1, f'c1 已接 2／可接 6（Lv45，q4～q9）／已完成 1（{c1!r}）')
        c3 = await d.inner_text('#crChars tr[data-crsel="c3"]')
        check('被擋住' in c3 and '正在打王' in c3 and '0／6／0' in c3, f'c3 被擋住＋why、可接 6 張（Lv32 只到 Lv30 組）（{c3!r}）')
        check('on' in (await d.get_attribute('#crChars tr[data-crsel="c1"]', 'class')).split(), 'cfg.ids 裡的 c1 是勾選的')
        grp = await d.locator('#crQuests .cr-grp').all_inner_texts()
        check(grp == ['Lv.20 以上', 'Lv.30 以上', 'Lv.40 以上'], f'任務依等級分組（{grp}）')
        cells = await d.locator('#crQuests tr[data-crq="q1"] td.cr-cell').all_inner_texts()
        check(cells == ['✓ 完成'], f'進度欄只列勾選的角色，q1＝已完成（{cells}）')
        check((await d.locator('#crQuests tr[data-crq="q3"] td.cr-cell').all_inner_texts()) == ['可領'] and (await d.locator('#crQuests tr[data-crq="q4"] td.cr-cell').all_inner_texts()) == ['沒接'], 'q3＝可領、q4＝沒接')
        opts = await d.locator('[data-crmap="q1"] option').all_inner_texts()
        check(await d.locator('[data-crmap="q1"]').input_value() == 'map1a' and '無BOSS' in opts[0] and '預設' in opts[0], f'地圖下拉預設 defaultMap，標示無BOSS（{opts}）')
        check('接取 十字獵人 2' in await d.inner_text('#crLog'), '最近紀錄')

        print('2. 點整列勾選 → POST /api/cross/cfg 改 ids；「設定」按鈕打開角色抽屜、不影響勾選')
        await d.click('#crChars tr[data-crsel="c3"] td:nth-child(3)'); await d.wait_for_timeout(800)
        check((last('/api/cross/cfg') or {}).get('ids') == ['c1', 'c3'], f'點 c3 整列 → ids=[c1,c3]（{last("/api/cross/cfg")}）')
        check('on' in (await d.get_attribute('#crChars tr[data-crsel="c3"]', 'class')).split(), 'c3 那列變成勾選')
        check(len(await d.locator('#crQuests tr[data-crq="q1"] td.cr-cell').all_inner_texts()) == 2, '任務總表多一欄 c3')
        await d.click('#crChars tr[data-crsel="c3"]'); await d.wait_for_timeout(800)
        check((last('/api/cross/cfg') or {}).get('ids') == ['c1'], '再點一次 → 移出')
        n0 = len(posts)
        await d.click('#crChars tr[data-crsel="c1"] button[data-rdcd="c1"]'); await d.wait_for_timeout(800)
        check(await d.locator('#charDrawer').count() == 1 and '本尊劍士' in await d.inner_text('#charDrawer h3'), '「設定」打開本尊劍士的角色抽屜')
        check(not any(p == '/api/cross/cfg' for p, _ in posts[n0:]), '按「設定」不會改勾選')
        await d.click('#charDrawer [data-cdclose]'); await d.wait_for_timeout(400)

        print('3. 開關、順序、地圖下拉（mapPref）、略過（skip）')
        await d.click('label:has(#crEnabled)'); await d.wait_for_timeout(800)
        check((last('/api/cross/cfg') or {}).get('enabled') is True, f'自動狩獵開 → enabled:true（{last("/api/cross/cfg")}）')
        await d.click('[data-crorder=high]'); await d.wait_for_timeout(800)
        check((last('/api/cross/cfg') or {}).get('order') == 'high' and await d.locator('[data-crorder=high].on').count() == 1, '順序 → 等級高的先')
        await d.select_option('[data-crmap="q2"]', 'map2b'); await d.wait_for_timeout(800)
        check((last('/api/cross/cfg') or {}).get('mapPref') == {'q2': 'map2b'}, f'地圖下拉 → mapPref（{last("/api/cross/cfg")}）')
        await d.evaluate('renderCross()'); await d.wait_for_timeout(3500)
        check(await d.locator('[data-crmap="q2"]').input_value() == 'map2b', '重畫後地圖下拉還是 map2b')
        await d.check('[data-crskip="q4"]'); await d.wait_for_timeout(800)
        check((last('/api/cross/cfg') or {}).get('skip') == ['q4'], f'略過 q4 → skip（{last("/api/cross/cfg")}）')
        check('2／5／1' in await d.inner_text('#crChars tr[data-crsel="c1"]'), '略過的不算可接（c1 可接 6→5）')

        print('4. 一鍵接取（確認框列出每隻要接幾張）、領獎')
        n0 = len(dialogs)
        await d.click('#crAccept'); await d.wait_for_timeout(1000)
        msg = dialogs[n0] if len(dialogs) > n0 else ''
        check('本尊劍士' in msg and '5 張' in msg, f'確認框列出本尊劍士 5 張（{msg!r}）')
        acc = last('/api/cross/accept') or {}
        check(acc.get('ids') == ['c1'] and 'q4' not in (acc.get('quests') or ['q4']) and 'q5' in (acc.get('quests') or []), f'POST /api/cross/accept ids=[c1]、quests 不含略過的 q4（{acc}）')
        check('2 項工作' in await d.inner_text('#crMsg'), '顯示送出幾項工作')
        await d.click('#crClaim'); await d.wait_for_timeout(1000)
        check((last('/api/cross/claim') or {}).get('ids') == ['c1'], f'POST /api/cross/claim ids=[c1]（{last("/api/cross/claim")}）')
        check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    print('\n全部通過' if ok else '\n有失敗項目'); sys.exit(0 if ok else 1)

if __name__ == '__main__': asyncio.run(main())
