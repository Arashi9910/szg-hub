# 測試（只在私人版，make-public 不會複製）

- `mockgame.js`：模擬上漲谷遊戲（3 個帳號、4 隻角色；掛機、撿取、自動販售、換圖、切換、鎖定、賣出、衝卷、神匠之魂、公會倉庫）
- `harness.py`：起模擬遊戲＋測試中控（複製 repo 到 /tmp/hub、關掉自動更新），用 Playwright 模擬每個 Chrome 設定檔跑竄改猴腳本
- `e2e_smoke.py`：冒煙測試

需要 Node.js、Python 3、`pip install playwright && playwright install chromium`。

```
cd tests && python3 e2e_smoke.py
```

模擬遊戲的格式以 2026-11-18 對照真實遊戲為準（見 HANDOFF.md「遊戲 API 重點」）。
