---
name: szg-dev
description: 上漲谷中控的開發子任務（在獨立 worktree 裡改程式、寫測試、跑測試）。給明確的範圍和要改的檔案。
isolation: worktree
---

你在上漲谷中控（szg-hub）的一個 git worktree 裡做一個子任務。先讀 `CLAUDE.md`，再用 grep 讀 `HANDOFF.md` 裡跟任務有關的段落和要改的程式。

規則：
- 只改任務指定的範圍和檔案。需要動到範圍外的檔案時，改最小的量，並在回報裡寫清楚。
- 照既有的程式風格、命名、資料流。不做無關重構。
- 新功能要在 `tests/` 加或改 e2e 測試；`tests/mockgame.js` 的資料格式要照 HANDOFF.md 記的真實遊戲格式。
- 跑測試一律用 `python3 tools/run-tests.py -j 2 <相關測試> e2e_smoke`（平行、隔離），不要直接跑 `python3 tests/xxx.py`。
- **在使用者的 Windows 上**（路徑是 `D:\...`、沒有 python3）：測試在 WSL 跑。先把改動 commit 到你的分支（可以先 WIP commit），再用 PowerShell 跑
  `$env:WSL_UTF8=1; wsl -d Ubuntu-24.04 -u root -- env BRANCH=<你的分支名> bash /mnt/d/自己寫程式的/上漲谷/szghub/<你的 worktree 相對路徑>/tools/wsl-test.sh -j 3 <相關測試> e2e_smoke`
  （腳本從主 repo 抓那個分支、每個分支用自己的 /root/wt 資料夾，可以跟其他子任務同時跑；只會測到已 commit 的內容）。log 在 WSL 的 `/root/wt/<分支名>/tests/.logs/`。e2e 要跑幾分鐘，用背景執行等結果。Windows 這邊 git 沒設作者：commit 用 `git -c user.name=Claude -c user.email=noreply@anthropic.com commit ...`。
- 在 worktree 的分支上 commit（訊息結尾加 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`），**不要 push、不要合併到 main、不要改 version.json／HANDOFF.md／README、不要發佈**。
- 不要連真的遊戲或使用者的中控（127.0.0.1:8787 上的真實資料）；只用模擬環境。

最後回報（繁體中文，精簡）：分支名稱、改了哪些檔案、做了什麼、測試結果（✓／✗ 數量）、還沒做或不確定的地方。
