# 上漲谷中控（szg-hub）— 給 Claude 的工作規則

私人 repo。最完整的技術細節、遊戲 API 格式、每一版的坑都在 `HANDOFF.md`，動手前先讀相關段落（用 grep 找，不要整份讀）。

## 使用者規則（一定要遵守）
- 給使用者的結論用繁體中文、先講結論。背景作業可以用英文。
- 動到遊戲資料、楓幣、不可逆的操作先問。道具可以處理，楓幣不要動。
- 私人版和公開版每次一起同步；公開版不能有個人資料和 Tailscale 設定。每次發佈都更新 changelog 和 HANDOFF.md。
- 清單要能點整列選取。
- 用 Chrome 開的分頁做完要關掉。
- 要對照「遊戲現場」：中控顯示的東西要拿真實遊戲畫面／資料比對，不能只看模擬環境。

## 架構
- `server.js`：中控伺服器（port 8787），API 在 `/api/*`
- `agent.js`：裝在遊戲分頁的腳本（Tampermonkey 載入），跟遊戲 API 溝通、回報給中控
- `bg.js`：背景 Chrome（CDP）
- `dashboard.html`：電腦面板；`m.html`：手機版
- `dest.js`：伺服器和面板共用的規則
- 遊戲 API：`POST /api/game` `{type, characterId, ...}`；副本指令加 `raidOnly:true`

## 測試
- `tests/mockgame.js` 模擬遊戲（9900），`tests/harness.py` 起測試用中控（8787，複製到 /tmp/hub）。
- **平行跑**：`python3 tools/run-tests.py -j 2 e2e_raid e2e_smoke`（每支在自己的網路命名空間＋自己的 /tmp，不會搶 port）。單支：`tools/isotest.sh tests/e2e_raid.py`。輸出在 `tests/.logs/`。
- 直接 `python3 tests/xxx.py` 會用到真的 8787／9900，同一時間只能跑一支。
- 改到哪個功能就跑相關測試＋`e2e_smoke`。新功能要加或改測試；mock 要照真實遊戲的格式（格式記在 HANDOFF.md）。
- claude.ai 雲端那台 2 核心：`-j` 最多 2～3。
- **使用者的 Windows（Claude Code）**：在 WSL `Ubuntu-24.04`（磁碟在 `D:\WSL\Ubuntu-24.04`，C 槽很滿不要放 C）跑。第一次裝工具 `wsl -d Ubuntu-24.04 -u root -- bash <tools/wsl-setup.sh 的 /mnt 路徑>`；跑測試 `wsl -d Ubuntu-24.04 -u root -- bash /mnt/d/自己寫程式的/上漲谷/szghub/<worktree>/tools/wsl-test.sh -j 6 e2e_xxx e2e_smoke`（`BRANCH=` 指定分支，預設 claude/project-folder-access-fd00e7；**只複製已 commit 的內容**，先 WIP commit）。20 核心，`-j` 可到 6～8。

## 平行開發的分工規則
- 每個子任務在自己的 worktree 做（`isolation: worktree`），**不要 commit 到 main、不要 push、不要發佈**；做完回報改了哪些檔、測試結果。由主對話合併和發佈。
- 同一個檔案（尤其 `dashboard.html`、`agent.js`、`server.js`）同時只給一個子任務大改；分工時依檔案或依區塊切開，避免合併衝突。
- 改 `version.json`、`HANDOFF.md`、`README` 只在主對話做（發佈時）。

## 發佈流程（只在主對話）
1. `version.json`：version、notes、notesPublic，changelog 最前面加這一版（items：type/name/what/how，只留 5 筆）
2. `HANDOFF.md` 第 3 行版本＋版本紀錄
3. commit／push 私人版（commit 結尾兩行 Co-Authored-By、Claude-Session）
4. `python3 tools/make-public.py /home/claude/szg-hub /home/claude/szg-hub-public`，視需要改公開版 README.md／docs/guide.md，commit，`git -c push.negotiate=true push`
5. 等約 3 分鐘，用 Claude in Chrome 開 `http://127.0.0.1:8787/` 比對 `(await fetch('/api/agent-version').then(r=>r.json())).version === '新版號'`，關分頁
6. 更新 claude.ai 專案文件 `claude/交接-目前進度.md`
