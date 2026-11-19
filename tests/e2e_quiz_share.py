"""共享題庫：tools/quiz-share.gs 的投票規則（用 mock_appscript.js 在 Node 裡跑真的程式）＋中控上傳／下載／合併"""
import asyncio, json, os, subprocess, sys, time
SHARE = 'http://127.0.0.1:9911/'
os.environ['SZG_QUIZ_SHARE_URL'] = SHARE
os.environ['SZG_QUIZ_VERIFY_MS'] = '4000'  # 面板答案等遊戲確認的時間（正式 30 分鐘）
from harness import Env, hub_json, http, HUB, HERE

ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ ') + msg)
    ok = ok and bool(cond)

def post(install, items): return json.loads(http('POST', SHARE, {'install': install, 'items': items})[1])
def bank(): return {x['q']: x for x in json.loads(http('GET', SHARE)[1])['items']}
A, B, C = 'a' * 24, 'b' * 24, 'c' * 24
Q1 = {'key': 'q1', 'q': '楓之谷的吉祥物是？', 'options': ['嫩寶', '菇菇寶貝', '綠水靈', '肥肥'], 'answer': '嫩寶'}

async def main():
    mock = subprocess.Popen(['node', os.path.join(HERE, 'mock_appscript.js'), '9911'], stdout=open('/tmp/mock_appscript.log', 'w'), stderr=subprocess.STDOUT)
    time.sleep(1)
    try:
        print('1. 試算表程式：投票規則')
        r = post(A, [Q1]); check(r == {'ok': True, 'added': 1, 'voted': 1}, f'新題目：{r}')
        check(bank()['楓之谷的吉祥物是？']['answer'] == '嫩寶', '下載得到')
        post(B, [{**Q1, 'answer': '菇菇寶貝'}])
        check('楓之谷的吉祥物是？' not in bank(), '兩個中控答案不同、同票 → 先不提供')
        post(C, [{**Q1, 'answer': '菇菇寶貝'}])
        b = bank()['楓之谷的吉祥物是？']; check(b['answer'] == '菇菇寶貝' and b['n'] == 2, f'多數決：{b}')
        r = post(C, [{**Q1, 'answer': '菇菇寶貝'}]); check(r['voted'] == 0, '同一個中控同一個答案只算一票')
        post(A, [{**Q1, 'answer': '菇菇寶貝'}]); check(bank()['楓之谷的吉祥物是？']['n'] == 3, '同一個中控改答案：票移過去（3 票）')
        r = post('xyz', [Q1]); check(r['ok'] is False, '匿名編號格式不對：拒絕')
        r = post(A, [{**Q1, 'key': 'q9', 'answer': '不在選項裡'}]); check(r['added'] == 0, '答案不在選項裡：不收')
        http('GET', SHARE + '__disable?key=q1'); check('楓之谷的吉祥物是？' not in bank(), '在試算表「停用」欄打 x → 不再提供')
        rl = [post(B, [])['ok'] for _ in range(45)]; check(rl.count(False) >= 1, '同一個中控 10 分鐘送太多次會被擋')
        http('GET', SHARE + '__rl')

        print('2. 中控：只上傳遊戲公布的正解')
        async with Env() as env:
            st = hub_json('GET', '/api/quiz')['share']
            check(st['on'] and st['configured'], f'預設加入共享題庫：{st}')
            hub_json('POST', '/api/quiz/learn', {'q': '轉職要去哪裡找導師？', 'options': ['維多利亞港', '魔法森林', '勇士之村', '弓箭手村'], 'answer': '魔法森林', 'by': '本尊劍士', 'correct': True})
            hub_json('POST', '/api/quiz/learn', {'q': '面板猜的題目', 'options': ['甲', '乙'], 'answer': '甲', 'by': '面板'})
            hub_json('POST', '/api/quiz/share/sync')
            rows = json.loads(http('GET', SHARE + '__sheet')[1])
            qs = [r[1] for r in rows[1:]]
            check('轉職要去哪裡找導師？' in qs, '遊戲公布的正解有上傳')
            check('面板猜的題目' not in qs, '自己在面板猜的不上傳')
            check(not any('本尊劍士' in json.dumps(r, ensure_ascii=False) for r in rows), '試算表裡沒有角色名稱')
            hub_json('POST', '/api/quiz/learn', {'q': '面板答了但沒選項的舊題', 'options': [], 'answer': '乙', 'by': '面板'})
            post(B, [{'key': '面板答了但沒選項的舊題', 'q': '面板答了但沒選項的舊題', 'options': ['甲', '乙'], 'answer': '甲'}])
            await asyncio.sleep(4.5); hub_json('POST', '/api/quiz/share/sync')
            rows = json.loads(http('GET', SHARE + '__sheet')[1]); qs = [r[1] for r in rows[1:]]
            check('面板猜的題目' in qs, '面板選的答案放過確認時間（沒被遊戲更正）→ 上傳')
            row = next((r for r in rows[1:] if r[1] == '面板答了但沒選項的舊題'), None)
            votes = json.loads(row[5]) if row else {}; check('乙' in votes and len(votes['乙']) == 1, f'沒存選項的：從共享題庫補選項後上傳（投自己的答案）：{row and row[3:6]}')

            print('3. 別人答過的題目：下載後直接能用')
            hub_json('POST', '/api/quiz/unknown', {'q': '最強的怪物是？', 'options': ['嫩寶', '殭屍菇菇', '巴洛古', '綠水靈']})
            post(B, [{'key': 'x', 'q': '最強的怪物是？', 'options': ['嫩寶', '殭屍菇菇', '巴洛古', '綠水靈'], 'answer': '巴洛古'}])
            hub_json('POST', '/api/quiz/share/sync')
            qz = hub_json('GET', '/api/quiz')
            check(qz['answers'].get('最強的怪物是') == '巴洛古' or any(v == '巴洛古' for v in qz['answers'].values()), '題庫裡有別人答的題目')
            check(not any(u['q'] == '最強的怪物是？' for u in qz['unknown']), '「等你作答」裡的那題自動消失')
            check(qz['srcCount'].get('shared', 0) >= 1 and qz['share']['count'] >= 2, f"題庫來源有共享題庫：{qz['srcCount']}")

            print('4. 面板')
            ctx = await env.browser.new_context(viewport={'width': 1400, 'height': 900}); env.contexts.append(ctx)
            d = await ctx.new_page(); errs = []; d.on('pageerror', lambda e: errs.append(str(e)))
            await d.goto(HUB + '/'); await d.wait_for_timeout(1500)
            await d.click('nav button[data-tab=quiz]'); await d.wait_for_timeout(1500)
            t = await d.inner_text('#qsStatus')
            check('共享題庫' in t and '已貢獻 3 題' in t, '狀態：' + t)
            await d.click('#qsOn'); await d.wait_for_timeout(1500)
            qz = hub_json('GET', '/api/quiz')
            check(qz['share']['on'] is False and not any(v == '巴洛古' for v in qz['answers'].values()), '關掉之後：不用共享題庫的答案')
            check('已關閉' in await d.inner_text('#qsStatus'), '面板顯示已關閉')
            check(not errs, '面板沒有 JS 錯誤' + ('：' + errs[0] if errs else ''))
    finally:
        mock.terminate()
    print('全部通過' if ok else '有失敗')
    sys.exit(0 if ok else 1)

asyncio.run(main())
