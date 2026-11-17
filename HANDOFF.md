# 上漲谷中控：開發交接筆記（私人，不同步到公開版）

最後更新：2026-11-18（v0.24.0）

## 環境與流程
- 私人 repo：本 repo（含 Tailscale／遠端設定）。公開 repo：`Arashi9910/szg-hub-public`。
- 每次更新的固定流程：
  1. 改 `version.json` 版本號與 notes（新增檔案要加進 `files`）
  2. commit／push 私人 repo（作者 Claude，結尾加 Co-Authored-By 與 Claude-Session 兩行）
  3. `python3 tools/make-public.py <私人repo路徑> <公開repo路徑>` 產生公開版（會拿掉 REMOTE／TOKEN／Tailscale，新增的程式檔要加進 `tools/make-public.py` 的 FILES）
  4. 更新公開 repo 的 README（公開版 README 獨立維護），commit 後 `git -c push.negotiate=true push`
  5. 在使用者面板分頁（http://127.0.0.1:8787/）執行 `/api/update/check` → `/api/update/apply` 套用；遊戲分頁約 2 分鐘內自動換新腳本
- 測試：`/home/claude/test`（mockgame.js 模擬遊戲、harness.py 共用工具、e2e_smoke.py 冒煙測試，`python3 e2e_smoke.py`）。harness 會把私人 repo 複製到 /tmp/hub 當測試中控，並先 `POST /api/settings {"autoUpdate":false}`，否則會被 GitHub 版本蓋掉。2026-11-18 舊測試檔隨舊工作階段消失，已重寫；**之後要放進 repo 才不會再不見**。
- 使用者規則：每次更新私人版與公開版一起同步；公開版不要放個人資料與 Tailscale 設定；**公會倉庫相關功能只做私人版**（公開版其他人做法可能不同），之後用程式標記讓 make-public 移除。

## 檔案
- `server.js` 中控伺服器（工作佇列、掛機、市場、題庫、DPS、掉落紀錄 /api/loot 只放記憶體）
- `agent.js` 遊戲頁面腳本（由 `szg-hub.user.js` 載入；旁聽頁面 fetch 取 DPS 與掉落）
- `dashboard.html` 面板（單一檔案）
- `market.js` 市場行情／自動上架；`extdb.js` 外部「冒險資料庫」（題庫、圖示、道具說明，執行時下載）
- `update.js` 自動更新；`quiz-bank.json` 內建題庫

## 遊戲 API 重點（/api/game）
- 需要 `X-Game-Version` 標頭（頁面 fetch 會加）；非 sync 動作要 requestId；「存檔忙碌」要重試（agent 的 `gameRetry`）
- 換圖 `{type:'map', map, characterId}`；切換角色 `{type:'switch'}`
- 自動販售 `{type:'autoSell', characterId, map, config:{enabled,itemIds}}`：**只接受角色目前所在地圖**
- 所有 /api/game 回應都是「整份狀態放最上層」（character、characters、tradeEligible…）＋ `summary`；頁面把它存成 `mapleSessionView = {state: 回應}`
- 批次衝卷（神匠之魂，2026-11-18 讀遊戲程式碼核對）：單件 `{type:'artisanScroll', uid, item, count(≤10), stopAfterSuccesses(0=不停), expectedSlots: g.slots, stopOnFail}`；多件把 `uid` 換成 `uids:[2～10]`。**每衝 1 次**扣 1 張卷軸＋10 萬楓幣（ARTISAN_FEE），失敗也扣格；卷軸要在同一隻角色身上，適用條件 `catalog.scrolls[id].target === gear.type`；詛咒卷軸失敗可能讓裝備消失。回應格式還沒實際看過。單次 `{type:'scroll', item, target, uid}`
- 公會倉庫（2026-11-18 實際存取 1 張卷軸核對）：`guildWarehouseView`、`guildWarehouseBatch {op:'deposit'|'withdraw', items:[{kind:'item', item:key, qty} | {kind:'gear', uid}](≤100), characterId}`。回應在 `summary.guildWarehouse = {guildName, mesos, cashPoints, items:{key:qty}, gear:[], capacity:{gear:500, items:500}, taxPercent:5}`；同步回應不會帶公倉內容。楓幣／點數是另外的 `guildWarehouseMesos`、`guildWarehouseCash`（使用者規則：不要動楓幣）。鎖定裝備、任務道具、不可交易的不能存。公會名「佐藤商會」，11 個帳號都在裡面
- 戰鬥事件在 sync 回應 `summary.events`（actor、damage、effectiveDamage、lines、skill、mob、killed）；冒險紀錄 `character.log`（「撿取：X × n」「自動販售：X × n，獲得 N 楓幣」）
- 目錄 `/api/catalog`：maps、mobs、mapDrops、drops、autoSellDrops（每張圖可販售的掉落）、skills、fourth（4 轉技能書：level、fee、bookDrops、books；技能書在背包「消耗」分頁）
- 傷害測試稻草人地圖 gms990040001／gms990040002（單人，產生 character.dpsReport）

## 目前功能（面板分頁）
總覽（需要處理、實戰 DPS 欄與明細、批次掛機）、裝備（清單／對照／撿到自動處理、同名合併）、交易、背包（依道具／依角色、含倉庫、跨角色賣出／鎖定／給某角色）、派工（工廠圖＋清單、匯入目前設定、目標掉落估算、自動販售範本、掉落動畫）、地圖（查詢、換圖、練功效率提示、組隊試算用實戰 DPS）、市場、知識王。

## 待辦（使用者已同意的方向）
1. 派工工廠圖持續依使用者回饋調整（操作手感、動畫）
2. **公會倉庫串接（僅私人版）**：過濾後的卷軸／裝備存入公倉，各角色依職業領取
3. **強化工坊**：衝裝規則（裝備種類、卷軸、成功幾次停、及格標準），先做「試跑」估算卷軸與楓幣，再用 artisanScroll 就地批次衝
4. **分流**：及格→鎖定／給適合的角色；不及格→商店或市場自動上架
5. 之後：打技能書路線（4 轉，使用者進度未到）

## 使用者偏好
- 繁體中文；先給結論；介面要一眼看懂、操作直覺，喜歡有「自動工廠」感的視覺
- 會動到遊戲資料、金錢、不可逆的操作要先確認；藥水會自動買，不需要提醒
