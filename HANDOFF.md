# 上漲谷中控：開發交接筆記（私人，不同步到公開版）

最後更新：2026-11-23（v0.60.1）

## 環境與流程
- 私人 repo：本 repo（含 Tailscale／遠端設定）。公開 repo：`Arashi9910/szg-hub-public`。
- 每次更新的固定流程：
  1. 改 `version.json` 版本號與 notes（新增檔案要加進 `files`），**並在 `changelog` 最前面加一筆、只留最近 5 筆**（{version, date, title, items:[{type: new|fix|change, name, what, how}]}；新功能一定要寫 how＝怎麼用；只在私人版的整筆或單項加 `private: true`，公開版要不同說法用 `whatPublic` 之類的 xxxPublic 欄位）。make-public 會檢查最前面那筆是不是這一版，不是就中止。
  2. commit／push 私人 repo（作者 Claude，結尾加 Co-Authored-By 與 Claude-Session 兩行）
  3. `python3 tools/make-public.py <私人repo路徑> <公開repo路徑>` 產生公開版（會拿掉 REMOTE／TOKEN／Tailscale，新增的程式檔要加進 `tools/make-public.py` 的 FILES）
  4. 更新公開 repo 的 README（公開版 README 獨立維護），commit 後 `git -c push.negotiate=true push`
  5. 在使用者面板分頁（http://127.0.0.1:8787/）執行 `/api/update/check` → `/api/update/apply` 套用；遊戲分頁約 2 分鐘內自動換新腳本
- **測試環境（全部在私人 repo 的 `tests/`，make-public 不會複製）**：
  - 新工作階段重建：`git clone` 私人 repo 到 `/home/claude/szg-hub`、公開 repo 到 `/home/claude/szg-hub-public`；需要 Node.js（目前 v22）、Python 3、`pip install --break-system-packages playwright && playwright install chromium`。
  - `mockgame.js`＝模擬遊戲（port 9900，3 個帳號 A1／A2／A3、4 隻角色 c1 本尊劍士／c2 本尊小號／c3 弓箭分身／c4 倉庫分身；`MOCK_MORE_ACCTS=1` 多 A4 c5 第四隻、A5 c6 第五隻）。常用環境變數：MOCK_PARTY=c3,c4（一開始的隊伍）、MOCK_PARTY_MSGS=40（真實大小的隊伍資料）、MOCK_BOSS_DPS、MOCK_BOSS_RESPAWN_MS、MOCK_MAP_STOPS_IDLE=1、MOCK_APPEARANCE=1（全身照 /api/appearance）；`harness.py` 的 `Env()` 會把私人 repo 複製到 `/tmp/hub` 當測試中控（port 8787，先關 autoUpdate），用 Playwright 模擬每個 Chrome 設定檔跑竄改猴腳本。log 在 `/tmp/mockgame.log`、`/tmp/hub.log`。
  - **注意 8787 port**：測試中控和使用者的中控同 port，但使用者的中控在他自己電腦上（透過 Chrome 的 127.0.0.1:8787），不會衝突；在雲端工作區跑測試只會用到 /tmp/hub。
  - 用公開版跑測試：`cp -r 公開repo /tmp/pubtest && python3 tools/make-public.py . /tmp/pubtest`，再 `SZG_REPO=/tmp/pubtest python3 e2e_xxx.py`。
  - 教學截圖：`SZG_REPO=/tmp/pubtest python3 tests/guide_shots.py /tmp/shots`，再複製到公開 repo `docs/images/guide/`。
  - 執行：`cd tests && python3 e2e_smoke.py`（每支印 ✓／✗，最後「全部通過」）。一支約 30 秒～2 分鐘，e2e_narrow 超過 2 分鐘要給長一點 timeout。e2e_dual_tab 偶爾不穩，重跑一次就過。
  - mock 測試控制：`/__mock/state`、`/__mock/additem`、`/__mock/addgear`、`/__mock/luck`、`/__mock/session`（見 mockgame.js 註解）。共享題庫用 `mock_appscript.js` 在 vm 跑真的 `tools/quiz-share.gs`，harness 預設把 `SZG_QUIZ_SHARE_URL` 指到 `http://127.0.0.1:9/`，測試不會碰到真的試算表。
  - 測試清單（42 支）：bg（約 4 分鐘）、smoke、boss_chain、boss_party4、mobile、boss_cards、dex、avatar、party、board_prune、revive、sell_race、agent_gate、bag_give、board_group、board_sync、boss、boss_party、delist、dual_tab、filters、forge、guild、guild_auto、guild_sell、guild_setup、guild_xfer、income、job_order、jobs_clear、lv_time、narrow、ov_switch、pets、quiz_share、roll_money、rollsell、split、switch、tab_routing、view_group（e2e_boss 約 4 分鐘、e2e_delist 約 3 分鐘）（檔名前面加 `e2e_`）。改到哪個功能就跑相關的幾支＋smoke。
- **實機驗證**：使用者的 Chrome（Claude in Chrome）開 http://127.0.0.1:8787/ 用 javascript 呼叫 API 看資料；做完要關掉自己開的分頁。不要直接開 play.szg08.com（會導到 /game/、中控腳本會在那個分頁跑），讀遊戲程式碼從 https://play.szg08.com/robots.txt 分頁 `fetch('/game/game.js')`，輸出只取識別字或計數（整段原始碼會被輸出過濾擋掉）。
- 使用者規則：每次更新私人版與公開版一起同步；公開版不要放個人資料與 Tailscale 設定（手機版 v0.53 起公開版也有，只能走 tailscale serve；遠端版腳本／REMOTE=1／共用通行碼仍只在私人版）。公會倉庫 v0.32 起公開版也有。
- 公開 repo 自己維護的檔案（make-public 不會覆蓋）：README.md、.gitignore、`docs/mobile.md`（手機版教學）、`docs/guide.md`＋`docs/images/guide/`（圖文安裝與使用教學）。功能有變動時記得順便更新這些文件。

- **新增工作種類時**：在 server.js 的 `KIND_MIN_AGENT` 登記最低腳本版本（私人種類寫在私人區塊裡），否則舊腳本的分頁會拿到工作然後「未知的工作類型」失敗。遊戲分頁有時會卡在舊腳本好幾版（Tampermonkey 快取），只能請使用者手動重新整理那個分頁。

- `/api/data` 只回傳最後 100 個工作，掛機指令很多時舊工作會被擠出清單；v0.30.1 加了 `POST /api/jobs/clear`（工作清單的一鍵清除）

## 檔案
- `server.js` 中控伺服器（工作佇列、掛機、市場、題庫、DPS、掉落紀錄 /api/loot 只放記憶體）
- `agent.js` 遊戲頁面腳本（由 `szg-hub.user.js` 載入；旁聽頁面 fetch 取 DPS 與掉落）
- `dashboard.html` 面板（單一檔案）
- `market.js` 市場行情／自動上架；`extdb.js` 外部「冒險資料庫」（題庫、圖示、道具說明，執行時下載）
- `update.js` 自動更新；`quiz-bank.json` 內建題庫
- `m.html` 手機版（v0.53 起公開版也有）

## 遊戲 API 重點（/api/game）
- 需要 `X-Game-Version` 標頭（頁面 fetch 會加）；非 sync 動作要 requestId；「存檔忙碌」要重試（agent 的 `gameRetry`）
- 換圖 `{type:'map', map, characterId}`；切換角色 `{type:'switch'}`。頁面重新載入時用 `sessionStorage.mapleCharacter` 決定角色，但**遊戲每次同步完會把它寫回畫面上的角色**（記憶體裡的 state），所以 agent 切換後要擋住這個寫入再立刻重新整理（v0.25.2）；伺服器的「目前角色」也會跟著頁面同步的角色走
- 自動販售 `{type:'autoSell', characterId, map, config:{enabled,itemIds}}`：**只接受角色目前所在地圖**
- 所有 /api/game 回應都是「整份狀態放最上層」（character、characters、tradeEligible…）＋ `summary`；頁面把它存成 `mapleSessionView = {state: 回應}`
- 批次衝卷（神匠之魂，2026-11-18 讀遊戲程式碼核對）：單件 `{type:'artisanScroll', uid, item, count(≤10), stopAfterSuccesses(0=不停), expectedSlots: g.slots, stopOnFail}`；多件把 `uid` 換成 `uids:[2～10]`。**每衝 1 次**扣 1 張卷軸＋10 萬楓幣（ARTISAN_FEE），失敗也扣格；卷軸要在同一隻角色身上，適用條件 `catalog.scrolls[id].target === gear.type`；詛咒卷軸失敗可能讓裝備消失。多件時遊戲要求**名稱、key、剩餘次數相同而且沒鎖定**。結果在 `character.lastArtisan`（單件 `{uid, attempts:[bool], successes, destroyed, slots, fee, stop}`；多件 `{multi:true, gear, selected, scroll, rate, items:[{attempts, successes, destroyed, slots, stop}], successes, lost, fee, stop}`；前者是讀遊戲程式碼推的，還沒實際衝過）。目錄 `catalog.scrolls[key] = {name, target, rate, cursed(失敗消失 %), stats}`。單次 `{type:'scroll', item, target, uid}`
- 公會倉庫（2026-11-18 實際存取 1 張卷軸核對）：`guildWarehouseView`、`guildWarehouseBatch {op:'deposit'|'withdraw', items:[{kind:'item', item:key, qty} | {kind:'gear', uid}](≤100), characterId}`。回應在 `summary.guildWarehouse = {guildName, mesos, cashPoints, items:{key:qty}, gear:[], capacity:{gear:500, items:500}, taxPercent:5}`；同步回應不會帶公倉內容。**單次請求另有伺服器上限**：98 種、10,658 張卷軸一次送會回「請求過大」（門檻不明，遊戲畫面只限 100 項），agent 會自動切半重送。楓幣／點數是另外的 `guildWarehouseMesos`、`guildWarehouseCash`，格式 `{type, op:'deposit'|'withdraw', amount, characterId}`（2026-11-19 從 /game/game.js 讀到；提領時遊戲畫面會跳稅金確認，taxPercent 5）。使用者規則：我自己操作時不要動楓幣；v0.34 起有「存楓幣／點數」功能，但一律要使用者逐一確認。鎖定裝備、任務道具、不可交易的不能存。公會名「佐藤商會」，11 個帳號都在裡面
- **野王（2026-11-20 讀 game.js＋實際資料核對）**：19 張野王地圖（catalog.maps[].bossSpawns：{mobId, minSeconds, maxSeconds}；多數有 `<地圖>_noboss` 版本）。王是**每隻角色一份**（instanceId `solo:角色:地圖`），同隊伍共用（`party:隊伍:地圖`，roster 列成員）。`{type:'sync', fullSync:true, includeBossRespawns:true, characterId}` 回 `bossRespawns:[{map, mapName, mob, name, instanceId, roster, scopeVersion, deadline, spawned, available}]`：available＝王已死、可付費重生（冷卻中，deadline＝預計重生時間，伺服器時間）；deadline 0 或已過且 available=false＝進地圖就會出現。戰鬥中的怪在同步回應最上層 `enemies:[{id, hp, maxHp, spawnId, damageBy…}]`。遊戲畫面寫「離開首領地圖，首領血量與冷卻會保留」。其他：`bossTimers`（最上層）、`character.bossCooldowns`、`bossCombatLocked`、`{type:'escapeBoss'}`（離開首領地圖）；`{type:'bossRespawn'}` 是付費重生（10 點或 1000 萬楓幣），**不用**。角色死亡判斷用 character.hp<=0（還沒實際遇過）。**換地圖（type:'map'）會停止掛機**（auto=false、until=換圖時間；2026-11-20 使用者實際打王發現，7 隻打完回原圖都沒在掛機）→ 換圖後要 `{type:'start'}`。
- **組隊（2026-11-21 讀 game.js）**：partyCreate、partyJoin {code}（隊伍代碼，可跨帳號）、partyLeave、partyKick {memberId}、partyInvite {code: 12 碼玩家 ID}／partyInviteAccept／partyInviteReject、partyFollow {memberId}（一鍵同圖；遊戲註明換圖後要重新開始掛機）、partyBuff。同步回應最上層 party = {code, leader, notice, messages, members:[{id, name, lv, job, map, auto, hp, maxhp, leader, self, mapInstanceId…}]}，accountParty＝帳號自己角色的隊伍代碼。最多 6 人（遊戲畫面）。partyJoin 的回應格式、隊長離隊後誰接隊長，還沒實際操作過。
- **死亡／復活（2026-11-21 讀 game.js）**：死亡＝character.hp <= 0（頁面 showDeath 跳 #deathDialog：「原地復活」送 `{type:'revive'}`、「暫時等待」只關視窗）。遊戲內建自動復活 `character.autoRevive`＝{enabled, max}（預設 enabled、max 3，每輪上限，0～99），`autoReviveUsed` 本輪已用，手動開始新一輪掛機才重算；設定 `{type:'autoRevive', characterId, config:{enabled, max}}`（從程式碼 token 推的格式，還沒實際送過）。每次死亡扣本級升級經驗 5%（最低 0 不降級），復活不延長掛機期限。其他欄位：deathAt、deaths、lastDeathXpLoss、autoReviveUsed。
- **賣給商店（2026-11-20 讀 game.js＋實測報價 1 疊、沒賣）**：`{type:'inventoryQuote', category, ids, characterId}`（ids＝堆疊 uid 或裝備 uid，遊戲自己也是 entry.uid）→ 報價單存在 **character.inventoryQuote** = {id, characterId, category, rows:[{uid, kind, key, name, qty, price, signature}], total, expiresAt}，**賣完也不清掉**；`{type:'inventorySell', quoteId}`。報價不會賣東西（遊戲的取消只是關視窗）。堆疊 uid 是 `stack:<角色>:inventory:<流水號>`、有 revision；同一道具常分好幾疊（9999 一疊）；裝備 uid `drop-<角色>-<序號>` 穩定。
- **自由市場攤位**：商品欄位只有 id、kind、key、name、icon、category、qty、price、description（**沒有上架時間**、遊戲不會自己到期）。下架 `{type:'marketCancel', listingId, characterId}`，東西回到該角色背包。
- 戰鬥事件在 sync 回應 `summary.events`（actor、damage、effectiveDamage、lines、skill、mob、killed）；冒險紀錄 `character.log`（「撿取：X × n」「自動販售：X × n，獲得 N 楓幣」）
- 目錄 `/api/catalog`：maps、mobs、mapDrops、drops、autoSellDrops（每張圖可販售的掉落）、skills、fourth（4 轉技能書：level、fee、bookDrops、books；技能書在背包「消耗」分頁）
- 傷害測試稻草人地圖 gms990040001／gms990040002（單人，產生 character.dpsReport）

## 目前功能（面板分頁）
總覽（需要處理、實戰 DPS 欄與明細、批次掛機）、裝備（清單／對照／撿到自動處理、同名合併）、交易、背包（依道具／依角色、含倉庫、跨角色賣出／鎖定／給某角色）、派工（工廠圖＋清單、匯入目前設定、目標掉落估算、自動販售範本、掉落動畫）、地圖（查詢、換圖、練功效率提示、組隊試算用實戰 DPS）、市場、知識王。
- **公倉（v0.25，僅私人版）**：存入選單（全部角色背包可存的東西→勾選→裝備用掉落浮動條件篩選→每隻角色一個 `guildDeposit` 工作）；公倉內容（`/api/guild` 存最後一次看到的內容；↻ 重新整理建立 `guildView` 工作，只讀所以自動排隊）→勾選＋給誰→`guildWithdraw`。裝備的建議對象＝冒險資料庫的職業＋等級，等級剛好夠的排最前面（使用者選「只建議，自己選」）。存入設定記在 settings.guildDep（names＝個別勾選、cats＝整類「卷軸」「裝備」）。
- **公倉自動存入（v0.26）**：settings.guildAuto `{mode:'off'|'preview'|'deposit', everyMin}`，server 每分鐘檢查、到時間就照 guildDep 替在線的目前角色建 `guildDeposit`（auto:true、直接 approved）；剛做完公倉工作、還沒回報新資料的角色跳過；公倉快滿就停。紀錄在 db.guildLog，`POST /api/guild/auto-run` 立即執行。
- 私人功能用 `<private:名稱>` … `</private:名稱>` 整行標記包起來（JS `//`、HTML `<!-- -->`），make-public 會整段移除並檢查公倉字樣沒有外漏；version.json 的 `notesPublic` 會變成公開版的 notes。

- **派工分組（v0.29）**：settings.boards = {A, B}（舊的 settings.board 當 A），settings.charGroup 覆寫分組（預設帳號角色清單第 1 隻＝A）；`boardGroup()` 自動＝有兩隻角色的帳號中目前角色多的那組。saveBoard 要存「當下那一份」並在 boardPending 期間讓 poll 保留本機設定（v0.29.1 修過一次被 poll 蓋掉的 bug）。看板只顯示該組角色（含沒同步過的，用 accountChars 補），非目前角色＝背景掛機，套用時略過。v0.29.2 裝備、交易分頁共用檢視組別 `ui.vg`（localStorage viewGroup；`snapsV()`／`allGear(true)`／`wearers()` 只看該組）。使用者不想看到兩組混在一起。使用者玩法：切換角色後另一隻在背景掛機，偶爾收菜。

## 待辦（2026-11-23 更新）
- 2026-11-23 新增：
  - 背景執行 v0.57.0：使用者 21:17 實機回報「可以登入正常執行，不會踢另一端，都正常」。v0.58 的帳號分頁、批次登入（Google ServiceLogin?Email= 預填沒官方文件，可能沒效，有複製 Email 備案）、顯示視窗還沒實機試。
  - 公倉自動更新：使用者問「在遊戲裡存東西，中控沒更新」。已回答（只有中控自己的公倉動作或按「重新整理」才會更新），並提議讓 agent 旁聽遊戲頁面自己的 guildWarehouseView／Batch 回應自動上傳（像 DPS／掉落那樣），使用者還沒回覆要不要做。
  - 使用者說「目標或販賣單獨拉出來」——問了是指什麼，他說先跳過。
  - 打王 v0.55～0.56 的連續打、隊伍分開打、依王決定，只在模擬環境測過；使用者的打王目前是關閉、partyMode=split，還沒實機跑過。實機第一次建議先試跑。
  - 手機版還沒做：推播（使用者說先不用）、手機上排隊伍成員、市場／公倉。
  - 圖文教學缺 Chrome 擴充功能頁、竄改猴安裝／設定頁的截圖（測試環境裝不了擴充功能）；使用者可以提供乾淨設定檔的截圖再補。
- 進行中／待回覆：
  - 使用者說「有些裝備圖片消失了」，查不到缺圖，問他哪一頁＋截圖，還沒回覆。
  - 楓幣收入 v0.39：遊戲 sessionReport.money 是淨額，含不含交易／給楓幣還沒證實（佐藤天司本次 -646 萬，原因未查）。
  - 公倉楓幣／點數的提領稅金（拿到 95% 或公倉多扣）真實遊戲還沒實際操作過。
- 使用者還沒選的 UI 建議：① 派工兩條工具列合併 ② 工廠圖連線穿過節點 ③ 背包頁整體重做 ④ 強化素質改數字方塊、結果改表格 ⑤「A組／B組／全部／自動」檢視切換和角色選擇器的分工講清楚 ⑥ 地圖頁紀錄改表格。
- 舊待辦：公倉裝備依職業一鍵分配、公倉同名裝備合併檢視、不及格裝備上架市場、4 轉技能書路線（使用者進度未到）、派工工廠圖依回饋持續調整。

## 使用者偏好
- 清單選取要「點整列」就能選（`tr.pickrow`＋勾選框的 data-*pick 屬性，共用點選／Shift 選一段的處理），不要只能點小勾選框
- 繁體中文；先給結論；介面要一眼看懂、操作直覺，喜歡有「自動工廠」感的視覺
- 會動到遊戲資料、金錢、不可逆的操作要先確認；藥水會自動買，不需要提醒
- 「可以操作存取道具，不要動到楓幣」：我自己測試時不碰楓幣／點數；楓幣點數功能一律要使用者確認
- 派工分 A／B 兩組，不要混在一起；公開版不放個人資料、Tailscale

## 升級時間（v0.31.0）
- 快照 `char.nextXp`（遊戲 `c.nextXp` 精確值，沒有時退回畫面算的 expNeed）、`nextXpExact`。
- server 收到精確值時寫 `db.expTable[lv]=nextXp`，`/api/data` 回 `expTable`。
- dashboard：`ORIG_EXP`（V113 公式）、`expNeed(lv)`（表內精確，否則原版×最接近已知等級倍率，標估計）、`lvTime(c,target)`、`ui.ovTarget`（localStorage ovTarget）、`#ovExpBox` 經驗表。測試 `tests/e2e_lv_time.py`。

## v0.32.0
- 公會倉庫已公開：程式裡的 `<private:guild>` 標記都拿掉了；make-public 的 `PRIVATE_WORDS` 目前是空的（之後有私人功能再加關鍵字＋區塊標記）。
- 存入規則 `settings.guildDep` 多 `chars`（null＝全部角色，陣列＝只這些；server `guildAutoTick` 也照它）；條件 `k:'_sum'`＝浮動總和（dashboard rollPass、server guildRollPass 都支援）。UI：#gGuideBox 引導（renderGuideSteps）、#gdSummary、data-gdpreset、data-gdgroup、#gdCats 動態類別。
- 工作排序：server `currentJobFor(code)` 依 `agentChar[code]`（/api/agent 輪詢帶的 charId）——排頭工作要的是另一隻角色時，先挑目前角色的 BAG_KINDS 工作。測試 `tests/e2e_job_order.py`、`tests/e2e_guild_setup.py`。
- mock：`/__mock/luck?seq=1,0,…` 控制衝卷成功／失敗順序（e2e_split 用，避免隨機失敗）。

## 雙分頁實測（2026-11-18，佐藤嵐思／嵐司）
- 同一個設定檔開第二個遊戲分頁、`sessionStorage.mapleCharacter` 設成另一隻再重新整理：兩隻都正常掛機、經驗速度正常（嵐思約 13M/h、嵐司約 53 萬/h，跟平常一樣），兩個分頁的快照都會即時回報，遊戲沒有踢人或報錯。
- 但：遊戲伺服器的 `activeCharacterId` 只在頁面載入（或 switch）時改，之後兩個分頁同步都不會改它 → 關掉第二個分頁後伺服器還記著嵐司，中控把嵐思當成背景角色。v0.32.1 讓 switch 也比對伺服器的 activeCharacterId。
- 分頁被藏到背景（同視窗另一個分頁在前面）時遊戲會進「離線掛機」、畫面暫停同步，切回來會跳「本輪掛機報告」，經驗照算。所以兩隻都要即時資料＝兩個分頁都要可見（兩個視窗）。
- 若要正式支援：中控「能不能操作」要改用「這隻有沒有自己的新快照」判斷，不能再用 activeCharId（guildAutoTick、看板、總覽切換、ovGroupBtns 都用到）。

## v0.33.0 雙分頁模式（正式）
- agent：`PAGE_ID`（每次載入）、`?szgChar=` 在 document-start 設 sessionStorage 後拿掉；`ck()` 讓 GM 鍵依角色分開（gameUpdateReloadAt、offlineSince、reloadForJob、reloadForUpdate）；`charTab:<角色>` 心跳＋`passive()` 防同一隻開兩個分頁；`lead:<code>`（amLeader）讓市場只由一個分頁做；`quizLock:<code>` 一次一個分頁作答；idleTick 不替有自己分頁的同帳號角色處理；`#szg-hub-open` 按鈕（window.open popup + noopener）；切換前 POST `/api/agent/leave`；背景分頁做工作前 `game({type:'sync'})` 取新資料。輪詢帶 page/hidden/off。
- server：`tabs[code][charId]`（/api/agent 輪詢更新，90 秒內算有分頁）、`routeOf`／`headFor`／`tradeHead`（每個分頁各自的工作頭；交易同帳號仍一次一個，peerReady＝對方要交易的那隻分頁的頭也是這個）、idle 依「交給哪個分頁」分組（`needChar`）、有分頁的角色 switch 擋下、wake 每個分頁各自；guild 自動存入／查看改用 tabOf；/api/data 回 `tabs`；push 不再用大廳資料蓋掉有分頁的同帳號角色。
- dashboard：`tabOf/hasTab/accTabs/charState/stateHtml/stateSuffix/tabTag`；activeCharOf 改成「有分頁的」；所有「目前角色」文字與判斷改成分頁模式；需要處理多「工作在等角色的分頁」、帳號層級的「沒回報」。
- 測試：`e2e_dual_tab.py`（瀏覽器兩個分頁）、`e2e_tab_routing.py`（伺服器派工，直接模擬輪詢含交易）。harness `open_account(acct, char)` 同 context 開第二個分頁；init script 只在 play.szg08.com 跑。mock 的回應依請求的 characterId 給角色。
- 待實機確認：非伺服器 activeCharacterId 的那隻用 characterId 換圖／衝卷是否被遊戲拒絕；知識王是每隻角色還是整個帳號一份（目前用鎖保守處理）。
- v0.33.1：實機發現頁面的 mapleSessionView 不一定會更新背包（鎖定後一直顯示沒鎖，分頁是看得到的）。agent `refreshOwnState()`：每 45 秒、工作前、工作後直接 `sync`，`readState()` 的背包相關欄位（OWN_KEYS）用這份。
- 實機確認（嵐思／嵐司雙分頁）：同一隻開兩個分頁會被擋；`?szgChar=` 免重整就生效；兩隻的鎖定／解鎖工作各自在自己的分頁完成（伺服器 activeCharacterId 不是那隻也可以）。
- v0.33.2：`becomeOther()`——剛開的分頁（90 秒內）發現這隻已有分頁、同帳號另一隻沒有 → 自動換過去（sessionStorage szgAutoOther 防重複，帳號 characterIds 來自 /api/account）。`TAB_ID`（sessionStorage szgTabId，只有 navigation type=reload 才沿用）讓 F5 認得自己。
- v0.33.3：窄螢幕 CSS（</style> 前那段）：header flex-wrap；≤1280px 時 `main :has(> table)` 左右捲、9 欄以上 min-width 980／13 欄以上 1200、`table.sticky` 的外框自己上下捲（表頭 top:0）；.fac-hud 換行。測試 `tests/e2e_narrow.py`（1080／864／720 每個分頁不撐破）。
- v0.33.4：強化試跑 `fgPlan()` 多 `cap`（budget＝min(卷軸, 楓幣/10萬)、canSure／canExp）、`rows[].maybeShort`、`expPassAvail`；pieces 依（已衝少、剩餘多）排序；`.fg-pickbar` data-fgsel=all/none/top/sure/exp、#fgTopN、#fgAllBox。面板有 approved/running 工作時每 3 秒 poll；forge 工作剛結束強制重抓 /api/forge。
- v0.33.5：背包「含公倉」（#bGuild，localStorage bagGuild）：`bagGuildRows()`，選取鍵 `G|g:uid`／`G|i:key` 放在 ui.bagSel（bagSelected 只看角色，賣出／鎖定不受影響）；動作列 `#bGuildTo` + data-bact=guildTake → guildWithdraw 工作直接 approve。
- v0.33.6：可讀性小改（body 14px、.sm 12px、tabular-nums、table.ov width:auto、--bad #e66b6b、:focus-visible）；header 的 #status/#updBox 收進 `#sysBox`（summary #sysSum 依狀態加 upd/warn/bad）；`.action-bar.idle`；tabTag 正常不顯示；公倉 #gdChars 全部角色時收起（#gdCharsCustom，ui.gdCharsOpen）。
- v0.34.0：
  - 浮動判斷分部位／武器：面板 `rollProfileDefault/rollProfile/rollJudge/rollFilterPass/rollEditorHTML`（settings.rollProfiles = {gtype: {stats, min}}），server `rollProfile` 同一套預設；條件 `{k:'_pass'}`＝依部位基準達標（不用填數字）。gearType：快照 g.gtype、公倉 g.type。
  - 公倉內容分頁 scroll/use/etc/gear（`itemKindOfKey`：快照類別 → WORLD.scrolls → 道具編號 204／2／3／4）。
  - 存楓幣／點數：工作 kind `guildMoney`（batches[0].mesos/cash），server 一律 pending、approve-all 跳過；agent `runGuildMoney` 先 guildWarehouseView、檢查身上夠、用 game()（不重試）存入、比對公倉餘額。面板「④ 存楓幣、點數」(#gmCard)。
  - 背包 view `list`（`bagListView`），工具列 #bJudge（ui.bag.judge 也套用到其他兩種看法）、data-bquick=rollno。
  - 測試：`tests/e2e_roll_money.py`；mock 新增 `/__mock/addgear`、`/__mock/additem`、guildWarehouseMesos/Cash、帳號 cashPoints。
  - 控制室風格改版（灰階、讀數列、需要處理加公倉快滿／知識王）先 `git stash`（ui-controlroom-wip），使用者說先處理功能，之後再接回。
  - ⚠ 讀遊戲原始碼時：開 https://play.szg08.com/ 首頁會被導到 /game/（中控腳本會跑），要從 /robots.txt 這類靜態頁面 fetch('/game/game.js')。
- v0.34.1：使用者更正——防具、手套只看四屬（力敏智幸），不看物攻魔攻；武器照舊。公倉楓幣／點數加提領（batches[0].op='withdraw'，agent 檢查公倉餘額、記錄身上前後差＝扣稅後實拿；mock 提領扣 taxPercent）；使用者要「全部確認」也能確認 guildMoney（面板確認框列出存入／提領合計）。面板切到提領或建立提領前會 loadGuild(true)（公倉餘額可能幾秒前的）。真實遊戲還沒實際存取過楓幣／點數，提領扣稅方式（拿到 95% 或公倉多扣）未證實。
- v0.35.0 介面改版第一步（使用者要的順序：總覽 → 公倉 → 背包）：
  - 總覽：stash 的控制室改版接回（石墨灰 :root、`--accent-fill`、SZG Num 數字字型 base64 內嵌、讀數列 `.gauges`、需要處理燈號＋公倉快滿／知識王，server `alertSummary()` 進 /api/data.alerts）。
  - 圖示：Lucide（ISC）內嵌 `ICONS` + `ic(name)`、靜態 `<span data-ic>` 用 `fillIcons()`。從 lucide-static 取 svg 內層 path（注意不要把外層 <svg> 一起抓進來）。
  - 公倉：`#gStatus` 狀態列（renderGuildStatus）、`.g-xfer` 三欄（左 `#gxBagOut` renderGuildBag／ui.gx，中 `#gxDeposit`＋`#gwBar`，右 `#gwOut`）、`#gRulesDrawer`（執行＋存入規則）、`#gMoneyDrawer`（楓幣點數）；Esc 關抽屜。存入（gxDepositPlan）與領取都直接 approve。測試 `tests/e2e_guild_xfer.py`；其他公倉測試要先點 `#gRulesOpen`／`#gMoneyOpen`。
  - 背包：角色卡收進 `<details id="bCharBox">`（localStorage bagCharsOpen）。
  - 參考：遊戲倉庫「背包與倉庫並排、中間按鈕搬移」（Opsive Storage Menu、Expressobits inventory transfer）、漸進揭露（少用設定收進抽屜）、GitLab 設定頁摘要。
- v0.36.0 功能整理（使用者同意的四步）：
  1. 入口分工：背包「給…」抽屜 `#bGiveDrawer`（giveOpen/renderGive/giveReqs，ui.give.src）取代交易頁分發（舊 #gFrom 程式碼留著但有 guard）；背包拿掉「含公倉」（ui.bag.guild 固定 false）和「存進公倉」（bagExtraActions 改成連到公倉）。
  2. 總覽「自動化」`#ovAuto`（autoItems/renderOvAuto，server `automationInfo()` 進 /api/data.auto）。
  3. 共用角色選擇器 `charPickHTML(id)`＋`CP[id]={get,set}`，spec {mode: all|A|B|tab|custom, ids}；as/mk 存 charSpec＋展開的 chars map（cpMapSync 動態同步，資料沒載入時不寫）；guildDep.charMode。類別順序 BAG_KIND_ORDER 裝備、卷軸、消耗、其他；裝備頁 #fJudge、公倉背包欄 #gxJudge。
  4. 部位設定：拿掉 slotStats 編輯器，穿戴對照 `statLineJ` 全部素質＋要看的加粗；條件 `_rollOk`／`_rollScore`（dashboard condVal、agent rollProf/ROLLP、market.js 由 server 注入 rollProfile）。`/api/autosell?v=` 沒帶或 < 0.36.0 的腳本拿不到用 _roll 條件的規則（舊腳本會當 0 全賣）。
  - 測試：新增 e2e_bag_give、e2e_filters、e2e_rollsell；刪除 e2e_bag_guild（功能移除）。
- v0.37.0：開關統一成 `input[type=checkbox].sw`（CSS 滑動開關，.pre＝試跑橘色）；總覽自動化改 `.auto-tile`＋`data-autotog`（AUTO_TOG 七個可切換；gear/mklist 開啟時 confirm 選直接或試跑，沒角色／規則會 alert 帶去設定）。`select[data-seg]`＋option data-short 由 `enhanceSegs()` 產生 `.mode-seg` 分段按鈕（select 隱藏，按鈕改值後觸發 change；測試要看 `.mode-seg` 不要看 select 是否可見）。表情符號換 Lucide（ic()／data-ic＋fillIcons()，renderAll 結尾會跑）。
- v0.38.0 共享題庫：Apps Script `tools/quiz-share.gs`（試算表「題庫」分頁：key、題目、選項、答案、票數、投票紀錄 {答案:[install]}、停用、更新時間；同票不提供；每 install 10 分鐘 40 次）。使用者的部署網址寫在 server.js `QUIZ_SHARE_URL`（公開版也用同一個，使用者同意預設加入）。server：`quizShareQueue`（/api/quiz/learn 帶 correct 欄位＝遊戲正解才排隊）、`quizShareSync` 每分鐘檢查（上傳 5 分鐘一次、下載 30 分鐘一次、新的「等你作答」觸發立即下載）、db.installId、db.quizShareState、db.quizShared；quizBank 順序 ext < bank < shared < learned。測試 `tests/e2e_quiz_share.py`＋`tests/mock_appscript.js`（vm 跑真的 .gs），環境變數 SZG_QUIZ_SHARE_URL 指向本機模擬。
- v0.38.1 補送：`quizShareSync` 先下載再掃 learned（`st.scanTo` 時間水位，含 by=面板 的，放 `SZG_QUIZ_VERIFY_MS`＝30 分鐘還沒被遊戲正解更正才送）；缺選項的從 ext／共享題庫補，補不到的記在 `st.optWait` 下次再試。取代舊的 `backfilled`（只送非面板的，導致 208 題只送了 2 題）。
- v0.39.0 楓幣收入：遊戲 `state.character.earned`（主控台累計賺得）與 `character.sessionReport`（money、xp、activeMs、startedAt、stoppedAt…，也有 soldItems／soldGear／purchased／used）；agent 快照 `char.earned`、`char.session`。dashboard `mesoRate(c)`＝session.money÷activeMs（≥10 分鐘才算），總覽讀數「楓幣收入／時」（只加掛機中的）、「合計賺得」（session.money 加總＋累計）；表格欄 mrate。mock `/__mock/session`，測試 `tests/e2e_income.py`。表格排序：null 一律排最後。v0.39.1：session.startedAt 是毫秒數字；session.money 是淨額（會是負的）；short() 支援負數。
  - 注意：使用者的 Chrome 登入多個 Google 帳號，直接開網址會跳 /u/5/ 顯示找不到；中控（Node、不帶 cookie）存取正常。
- v0.40.0 總覽小怪：素材在 `tools/pets/<怪物>/<動作>_<n>.png`（slime、mush，動作 stand／move／jump／hit1／die1），`python3 tools/build-pets.py` 轉 base64 寫進 dashboard.html 的 `// <pets-data>` 區塊（換圖或加怪物就重跑）。程式 `PET_DEF`（名字、速度、台詞）、`petsInit/petTick/petClick`，#ovPetsCard；原圖臉朝左，往右走用 scaleX(-1)。點擊：連點 5 下（1.5 秒內）倒下 3 秒後隨機位置復活，其他隨機被打退／跳／逃跑／愛心。localStorage ovPets=0 收起。使用者說素材「先暫時放置」，之後可能換。測試 `tests/e2e_pets.py`。
- v0.41.0 輪流打野王＋攤位逾時下架：
  - 野王：settings.boss `{mode: off|preview|auto, chars, charSpec, mobs: null=全部|[mob], estMax 分, visitMax 分}`；db.boss `{state:{角色:{at, offset(伺服器時間差), list}}, hp:{instanceId:{hp,maxHp,at}}, last:{角色|mob:{at,result}}, home:{角色:原地圖}, homeName, log, seen}`。server `bossTick()` 每分鐘：角色要有自己的分頁、在掛機、沒有進行中的工作、狀態 20 分鐘內；`bossRows()` 算 ready／cooling／預估（hp÷實戰 DPS w60）／skip（沒勾、冷卻、預估超過 estMax、30 分鐘內失敗過 BOSS_RETRY_MS）；同 instanceId 不重複派；預估快的先。工作 kind `boss`（BAG_KINDS，KIND_MIN_AGENT 0.41.0，直接 approved）。API：GET /api/boss、/api/boss/need、POST /api/boss/state、/hp、/result、/run-now。
  - agent：`bossStateTick`（中控說需要時每 4 分鐘 fullSync 回報，開頁 15 秒後第一次）；`runBossJob`：同步確認王（冷卻就不去）→ 原地圖用剛同步到的 character.map（頁面的 mapleSessionView 可能是舊的，實測踩過）→ map → 每 4 秒 sync 看 enemies 的王血量，結果 killed／timeout／dead／absent（45 秒沒看到王）／stuck（3 分鐘血沒降）／moved（被換圖就不帶回）→ 回原地圖（失敗就 escapeBoss 再試）→ 回報 hp（打死清掉）與 result。
  - 面板：地圖頁 #bossCard（CP.boss 角色選擇器，預設不勾任何角色；#bossMobs 王清單；#bossTable 狀態、血條 .hpbar、預估、備註）；總覽自動化磁磚 boss、delist（只顯示，不能直接開，避免誤開）。
  - 逾時下架：market.js `trackAge`（m.age[角色][listingId] = {first, qty}，數量變少重新計時；不管開關都在記，所以開啟時已經累積）；settings.market.delistMode／delistHours；reportStall 回 `delist` 清單 → agent stallTick `delistOverdue`（marketCancel，裝備比對下架前後背包找新 uid）→ POST /api/market/delisted 記進 m.blocked（'i:道具key'／'g:裝備uid'），plan() 略過。/api/market/unblock {k|'*'}。攤位每 5 分鐘回報一次（GM 值 testStallMs 只給測試縮短），檢查間隔改 20 秒。
  - 待實機確認：真實遊戲打王時角色會不會優先打王、王死後 enemies 是否立刻消失、角色倒下的欄位、隊伍共用時兩隻同時被派的情況、marketCancel 回應裡的裝備 uid。第一次實際出動請使用者確認後只用一隻角色、一隻王試。
- v0.41.1 野王以隊伍為單位：server `partyMap()` 從各角色快照的 `party.party`（{code, members:[{id, name, lv, map, auto, leader, self…}]}，30 分鐘內、2 人以上）建「角色→隊伍代碼」；`bossUnitOf()`；`bossTick` 以 unit 為單位：勾了其中一隻＝整隊（有分頁、在掛機、沒工作的 `bossAvail`）一起出發打同一隻王，預估用 DPS 加總，任一隊員還在打王就整隊等；每人一個 boss 工作（batches[0].boss.party＝隊員名字），各自回自己的 home。/api/boss 的 chars 多 party、partyDps、picked（on＝隊伍有人被勾）。面板 .boss-grp 同隊放一起。mock：環境變數 MOCK_PARTY=c3,c4（王改成依 instanceId 存在 bossStore）。測試 `tests/e2e_boss_party.py`。
  - 2026-11-20 使用者的隊伍：嵐思＋嵐濕、打幣9＋打幣10、打幣12＋盜賊；隆司、起司各自一人一隊（一人隊伍當單人處理）。
- v0.41.2 打王修正（第一次實際使用的回饋）：
  - 實測：首輪 7 隻 30 秒內打死（因為「掛機續掛」剛好在首領地圖重開掛機），回原圖後沒在掛機；第二輪王血量 100% 不動、3 分鐘後放棄。修正：runBossJob 到首領地圖、回原圖後都 `start`；打王中 character.auto=false 每 20 秒再 start。mock 環境變數 MOCK_MAP_STOPS_IDLE=1 模擬換圖停掛機（boss 測試有開）。
  - 即時進度：agent 每 4 秒 POST /api/boss/hp；server `bossHpTrack`（記憶體）＋`bossLive()` → /api/boss 的 `live:[{instanceId, mob, name, mapName, names, startedAt, hp, maxHp, hpAt, perMin, etaSec, msg}]`；面板有進行中時每 3 秒重抓。
  - 面板改版：#bossLive（進行中血條）、#bossGrid（王 × 出發單位總表，格子 .bc ok／busy／cd／skip，滑鼠看原因；名字共同前綴省略）、設定收進 #bossSetBox（摘要 #bossSetSum）。
  - 快速擊殺：12 秒內沒看到王就查一次 bossRespawns，已冷卻＝打死（不再誤判「王不在」）。
  - 使用者覺得原本 UI 太亂、操作麻煩；改版後待他回饋。我在 17:22 把 boss.mode 關掉並替 7 隻角色重開掛機，要他確認後再開。
- v0.42.0 派工與遊戲雙向同步（使用者常直接在遊戲裡設定，看板抓不到）：
  - 看板資料：assign＝**還沒套用**的派工（套用後就刪掉），角色顯示位置＝assign 或「實際地圖（在看板上的話）」；sell＝每張圖的販售範本。
  - dashboard `boardSyncFromGame()`（poll 每次跑；S.boardSync !== false 預設開）：比對 settings.boardSeen[角色]＝{map, sell:{地圖: sellKey}}（存在設定裡，中控沒開時的變化也抓得到）。角色所在地圖不在看板→放進「練功」；遊戲換了圖（和 seen 不同）且有不同的 assign→刪掉 assign（以遊戲為準）；某張圖的 autoSellAll 和 seen 不同→更新 sell 範本（第一次同步只補沒有的範本）。改的是角色所屬組別（charGroup）的看板。有打王工作的角色跳過。boardPending（看板正在存）時跳過這輪。紀錄 settings.boardSyncLog（30 筆），工具列 #bdSyncBox（#bdSync 開關＋最近紀錄）。測試 `tests/e2e_board_sync.py`。
- v0.43.0（使用者實測打王回饋）：
  - 發呆原因：開司等幾個分頁還在跑 0.41.1 舊腳本（沒有換圖後 start），Tampermonkey 快取；19:10 時嵐司 0.41.1、打幣9 0.41.2、嵐濕／打幣1 0.42.0。KIND_MIN_AGENT.boss 提到 0.43.0 → 舊腳本分頁接到打王工作會先重新整理換新腳本。
  - 掛機設定組合（2026-11-20 讀 game.js）：遊戲有 3 套「掛機設定」（藥水、技能、自動復活、目標等），`{type:'settingsPreset', slot: 1|2|3}`，目前那套在 `character.settingsSlot`（沒設定過＝沒有這個欄位＝1）；遊戲說明「三套各自獨立，第一次切到沒用過的那一套是空白的」。settings.boss.presetBoss（0＝不切換）、presetTrain（0＝換回出發前那套）；runBossJob 到首領地圖先 settingsPreset 再 start，回練功圖同樣先切再 start。快照多 char.settingsSlot。mock 的 settingsPreset 記在 c.presetLog（e2e_boss 檢查順序）。
- v0.43.1 開分頁按鈕（有人回報「第二隻的分頁關掉後，右下角開分頁的選項消失、開不回來」）：模擬環境三種情境（按鈕開→關、直接開新分頁自動換→關→A 重新整理、關掉第一個分頁）都重現不出來。推測是真實 Tampermonkey 關視窗時 pagehide 的 GM_setValue（at:0）沒寫進去，或舊的 ✕（7 天不顯示）。改成按鈕永不整個消失：`accountCharList()`（頁面 characters → 沒有就用 account.characterIds＋GM 記的 charNames:<code>）；有分頁的角色顯示灰色「X 已開」（data-szghas，title 寫幾秒後恢復；按了 confirm 後照開，重複的分頁會自動 passive）；✕ 改成 sessionStorage szgOpenMini 收成「＋ 分頁」。e2e_dual_tab 的斷言跟著改。若之後再回報，要問清楚：公開版還是私人版、哪個版本、按鈕是灰的還是完全沒有。
- v0.43.2：打王一直輪流時中控更新會卡住（自動更新與 /api/update/apply 都要「沒有進行中的工作」）。`updateBlockers()` 不算 idle、boss 工作；遊戲分頁的 userscript 會等 isBusy()（agentBusy/agentRunning）結束才重新整理，所以打王中不會被打斷。
- v0.43.3：打王的分頁在 runBossJob 迴圈裡（agentRunning）不會來 /api/agent 問工作 → 90 秒後中控以為分頁不見（tabs 沒有它），routeOf 把工作轉給同帳號另一個分頁，那邊一直回報「等待 某某 的遊戲分頁」蓋掉 lastMsg（實機 20:17 看到）。新增 GET /api/agent/beat（只 seenTab），agent 在 agentRunning 時每 20 秒打一次。e2e_boss 有檢查。
- v0.43.4 賣出「報價單有 28 項，比選擇的 13 項多，已停止」（使用者轉述別人回報，背包有變動時發生）：推測送出的 id 對不上（掛機撿東西改變堆疊）時遊戲沒產生新報價，回應裡是角色身上舊的 inventoryQuote（或同角色同時有別的報價）。agent `safeQuote(charId, category, ids)`：報價前 sync 記下舊報價 id → 報價 → 一定要是新 id、category 相同、每列 uid 都在選的清單裡（不對就等一下重試一次，第二次才報錯）。賣出道具改用剛同步的背包「依 key 重新挑所有沒鎖的堆疊」（以前用工作裡的舊 uid，uid 是流水號可能對到別的東西）。三個地方都改：背包賣出、撿到裝備自動賣、公倉賣出。mock：inventoryQuote 存在 c.inventoryQuote、id 有任何一個對不上就不產生新報價；/__mock/restack。測試 `tests/e2e_sell_race.py`。
- v0.44.0 死掉自動原地復活：idlePolicy.autoRevive（預設開，/api/idle-policy 回 autoRevive !== false）、reviveMaxPerHour（預設 6）。agent idleTick → `reviveTick`：目前角色 hp<=0；同帳號沒有自己分頁的角色（characters 清單沒 hp 時，沒在掛機的每 2 分鐘 sync 一次確認）→ `revive` → 回應的 character.auto 是 false 就 start → 自己的頁面關掉 #deathDialog。每隻每小時次數存 GM `revives:<id>`，超過上限就 idle-log kind:'reviveLimit'（一小時通知一次），總覽「需要處理」列「死太多次」。idle-log 多存 kind。mock：`revive`、/__mock/die。測試 `tests/e2e_revive.py`。
- v0.44.1：使用者要求每小時復活上限可設到 9999（#ipReviveMax max 9999，預設 6 不變）。
- v0.45.0 派工空地圖自動移除（使用者要求「地圖沒有接點時自動刪除」）：dashboard `boardPruneEmpty()`（poll 每次跑，在 boardSyncFromGame 之後）。地圖「有人」＝看板 assign 指到它（不分組、不含 __pool），或該組角色的實際地圖是它（assign 是 __pool 的不算），或角色有進行中的打王工作而 boss.back 是它。沒人就在 settings.boardEmpty[組][地圖] 記開始時間，超過 S.boardPruneMin（預設 10 分，可小數，測試用 0.3）就從 lanes 移除，sell／goals 保留，紀錄寫進 boardSyncLog。開關 S.boardPrune（預設開，#bdPrune 在 #bdSyncBox）。不能存在 board 物件裡：boardCfg() 只複製固定欄位，saveBoard 會洗掉。測試 `tests/e2e_board_prune.py`。
- v0.46.0 組隊分頁＋即時經驗（使用者：用派工排組隊不方便、換圖後要很久才看得出效果）：
  - 即時經驗：server `expSample(snap)`（/api/push 每次）存每隻 {t, lv, xp, need}（記憶體，15 分鐘），`expRate` 跨等級用 need＋db.expTable 補；key＝地圖|隊伍代碼，變了就把前 10 分鐘速度存成 base、since＝現在（只用換之後的資料）；`expLive()` 進 /api/data.expLive[角色] = {rate（最近 3 分鐘，資料滿 50 秒才有）, span, since, base}，超過 90 秒沒新資料的不列（分頁關掉、離線掛機）。總覽每小時經驗欄下面「近3分」。
  - 組隊：settings.parties = [{id, name, members（第一位隊長）, map}]。/api/party/apply → `applyParties()`：每個隊員一個 party 工作（BAG_KINDS，KIND_MIN_AGENT 0.46.0），隊伍已經是這幾個人（partyMap 判斷）就 ops=false 只換圖＋start；db.partyRuns[runId]={leader, members, code…}。agent `runPartyJob`：ops 時先 partyLeave（sync 看 party.code）→ leader partyCreate → code（回應或再 sync 的 party.code）POST /api/party/code → member 每 3 秒 GET /api/party/run 等 code（最多 150 秒；隊長工作失敗就回 error）→ partyJoin → 換圖（不同才換）→ start。
  - 面板 #party：#ptPool（還沒分隊）、#ptCards（.pt-card data-ptdrop、.pt-mem／.pt-chip data-ptchar 可拖曳＝HTML5 DnD dataTransfer 'text/szg-pt'，或點選 ui.pt.sel 再點卡片）、👑 data-ptlead 設隊長、#ptImport（遊戲目前隊伍，大家同一張圖才設地圖）、#ptSuggest（planGroups()：從 runPlanner 抽出來共用，只排有分頁的角色）、ptStatus（套用中／失敗／已就位／要套用的差異）、ptLive（全隊近 3 分合計、出發前比較）、ptEstimate（groupEstimate 試算）。
  - mock：隊伍改成動態 parties（partyCreate／Join／Leave，c.partyCode），MOCK_PARTY 變成一開始的隊伍；simulate 找不到怪物時不再丟 500。測試 `tests/e2e_party.py`。
- v0.47.0 組隊為主的派工＋全身照＋3D 流水線（使用者：「派工能不能跟組隊結合？卡片只有名字難看，人物那邊有全身照」→ 選「組隊為主」；「派工主要是看特效、看自動化賞心悅目，也希望更直覺，用 three.js 做成有特色的視覺流水線」）：
  - 全身照：遊戲頁面全域 `MapleAppearance`（appearance.js）`key(c,'attack')`、`load(c,'attack')` → {stand: 78×78 站姿 GIF 的 blob URL}。agent `uploadAvatar`／`avatarTick`（開頁 20 秒後、之後每 5 分鐘；key 沒變就不傳，GM `avatarKey:<id>`；同帳號沒分頁的角色 30 分鐘 sync 一次再傳）→ POST /api/avatar {charId, key, gif(base64)} → data/avatars/<id>.gif，GET /api/avatar/<id>；/api/data.avatars = {id: 時間}。面板 `avatarImg(id)`（還沒有就 👤）；組隊卡片隊員改成直立小卡（全身照＋名字＋等級＋地圖＋近 3 分），角色池 chip 有小頭像。mock：MOCK_APPEARANCE=1 放一張 40×40 的 GIF。
  - 組隊套用帶自動販售：ptApply 把派工看板（A、B 都找）那張圖的 sell 範本一起送；server party 工作 `sell`，agent runPartyJob 換圖後 `autoSell`。KIND_MIN_AGENT.party → 0.47.0（舊分頁會先重新整理）。
  - 流水線：派工檢視多一個「✨ 流水線」（ui.board.view='pipe'，#bdPipe）。dashboard `pipeModel()`：每個組隊（S.parties）一座平台，沒排進隊伍、在看板地圖或有分頁的該組角色各一座小平台 → 地圖站（看板上的圖＋平台所在的圖，顏色＝路線）→ 經驗／商店／背包。管線粒子數量和速度跟著 expLive（對數）；狀態色：ok 藍、移動中黃、待套用橘、打王紅、背景灰。掉落（pollLoot 在 pipe 檢視時改呼叫 pipeLoot）變成沿管線飛的光球＋CSS2D 道具圖示（外部圖片不能當 WebGL 貼圖）。點隊伍→組隊分頁（卡片閃一下）、點地圖站→自動販售設定、點經驗／背包→總覽／背包。鏡頭依內容自動對準，使用者轉過就記在 localStorage p3dCam，「⟲ 視角」重設。看不到（換分頁、視窗隱藏）就不畫。沒有 WebGL 時顯示「改看工廠圖」。window.__pipe（frames、orbs）給測試用。
  - 測試 `tests/e2e_pipe.py`（headless SwiftShader 約 1 fps，所以斷言不靠動畫時間）。
- v0.47.1：使用者實機 14 座平台排成一長條、名字疊在一起 → 平台每欄最多 6 座、多欄錯開，鏡頭改由上往下（fit 依欄數和列數）。
- v0.47.2：實機 19 個分頁換到 0.47 後全身照仍是 0 張（appearance.js 確認是 globalThis.MapleAppearance、load 回 {stand: GIF blob URL}）。改用 W.fetch 讀 blob，並加 POST /api/avatar/diag、GET /api/avatar-diag（記憶體）回報每隻失敗在哪一步（noMA／key／load／nostand／blob／b64／post）。
- v0.47.3：avatar-diag 回報全部是「blob:Failed to fetch」（頁面讀 load() 的 blob: 網址失敗，可能是 CSP 或快取已 revoke）。改成直接 `W.fetch('/api/appearance?' + MA.key(c) + '&action=stand')`（appearance.js 的 fetchPart 就是這樣抓；key(c) 是 URLSearchParams 字串），不再呼叫 load。mock 有 /api/appearance（harness 對這個路徑用二進位轉送）。
- v0.48.0：使用者覺得 3D 流水線「構想還行但太吃資源」，要回 2D、但一樣顯示人物圖，總覽也要。→ 拿掉 pipeline3d.mjs／three-bundle.mjs、server 路由、派工「流水線」按鈕（localStorage boardView='pipe' 自動改回 factory；更新器不會刪舊檔，使用者資料夾裡可能還留著那兩個檔，無害）。`avatarSrc`／`avatarImg(id, cls)` 移到 `let DATA` 後面（總覽先用到）；全身照出現在：總覽角色欄（.ava.ov 40px）、工廠圖角色節點（.ava.fn 52px，預設節點間距 84→100）、清單角色卡（.ava.bc）、組隊卡片／池。測試 e2e_pipe 改名 `tests/e2e_avatar.py`。3D 版做法（three.js 打包、bloom、CSS2D 掉落圖示）留在 git 歷史 v0.47.x，如果之後想要輕量版可以參考。
- v0.49.0 裝備圖鑑（使用者：新分頁顯示所有裝備，基本素質＋浮動，依職業、等級分類；選某職業時全職業也要顯示）：
  - 資料：agent uploadWorld（版本前綴 w5）多送 `equipment`＝[id, 名稱, equipmentType, subCategory|category, reqLevel, reqJob(位元，0 全職業、-1 一件初心者), 標準素質{inc*}, tuc, [reqSTR,DEX,INT,LUK]]，排除 meta.cash；`statNames`。真實 catalog.equipment 1035 件，素質在 meta.incX（mock 是 base）。
  - 浮動範圍是推估：用使用者 24 隻角色約 3,600 筆 cleanStats−baseStats 對出 `±max(1, ceil(標準×10%))`，物攻／魔攻最多 ±5（PAD 85 有 405 筆，最大 5），其他最多 ±10（PDD 132 最大 10）。遊戲程式碼裡沒有規則（伺服器端擲骰）。函式 `dexFloat`。
  - 面板 #dex：職業 seg（全部／全職業＝只 reqJob 0／各職業＝只該職業，v0.49.1 使用者要求不混全職業）、等級（區間按鈕、自訂最低最高、「我的角色可穿」＝有角色等級夠且職業位元符合）、部位 chip（武器合一類，點了再展開武器種類）、搜尋、排序（等級／部位／攻擊）、只看我有的（snaps 的 gear itemId 計數）。設定存 localStorage 'dex'；一次顯示 120 件，「再顯示」加 240。測試 `tests/e2e_dex.py`。
- v0.50.0 圖鑑掉落來源（使用者：要知道每件裝備去哪張圖、打誰會掉，能連到地圖或派工）：`dexDrops(id)`（WORLD.maps × mobs × dropsFor 建反查索引，WORLD.version 變才重算）；卡片「▸ 掉落 N 處・最高 x% 怪＠圖」，點開（ui.dex.open，卡片變兩欄寬）列前 30 處，`data-dexmap` → `dexGotoMap`（切到地圖分頁、清篩選、搜尋框填圖名、ui.wOpen 展開、捲過去）；`data-dexboard` → confirm 後 `dexToBoard`（目前組別看板：不在看板上就放進 lanes.gear，goals[地圖] 加這件），只改看板不移動角色。「只看有怪物掉的」d.drop。
- v0.51.0 野王改成每隻角色各自勾王（使用者：「A 去打誰誰誰、B 去打誰誰誰」，不要 ABC 共用一份王清單，要卡片式）：
  - 設定 settings.boss.charMobs = {角色: ['*']（全部）| [mob…]}；沒有 charMobs 時從舊的 chars＋mobs 換算（server `bossCharMobs`、dashboard 同名函式同規則）。chars 由 charMobs 推出（agent /api/boss/need 還在用），dashboard saveBoss 會把 mobs 設 null、刪 charSpec。CP.boss 角色選擇器拿掉。
  - server：bossRows(charId, dps, allow)，`bossAllow(unit, c)`＝隊員勾的聯集；bossTick、bossSummary 都用隊伍的聯集；/api/boss chars[].mobs。
  - 面板：地圖頁打王卡片裡 #bossWhoBox（預設展開）→ #bossCards `.bk` 每隻角色一張（全身照、等級、隊伍、沒分頁／沒掛機的 !），王 chip `.bk-mob`（data-bkmob="角色|mob"；'*' 顯示「全部的王」，點了變成逐一挑選、先全勾），虛線＝隊友勾的、淡色＝王比角色高 10 級以上；動作 全部／等級內（王等級 ≤ 角色）／複製給…（套用到其他有勾的角色，confirm）／清除。搜尋、只看有勾的。測試 `tests/e2e_boss_cards.py`。
- v0.52.0 手機版（私人版，使用者：先做私人版、手機要能操作、推播先不用）：
  - 連線：建議使用者在電腦執行一次 `tailscale serve --bg 8787`（HTTPS，網址 https://機器名.xxx.ts.net，伺服器不用 REMOTE=1）。經 serve 轉送的請求來源是 127.0.0.1，所以 `isLocal()` 看到 x-forwarded-for／x-forwarded-proto／tailscale-user-login 就當遠端（要通行碼、不能更新）。
  - 配對：db.mDevices = [{id, name, token, at, seenAt}]，`tokenOk` 也接受裝置通行碼（timingSafeEqual），seenAt 每分鐘更新一次。/api/m/pair、/api/m/revoke、/api/m/devices、/api/m/info（`tailscale status --json` 拿 Self.DNSName）只限本機。面板右上「📱 手機」#mBox：網址（localStorage mBase，預設 https://DNSName）、新增 → QR（內嵌 qrcode-generator 2.0.4 MIT，`<script>` 在 private 區塊）網址 `/m#t=裝置通行碼`、裝置清單＋移除。
  - /m、/m/manifest.webmanifest、/m/icon.svg 不用通行碼（頁面沒有資料）。m.html 從 #t= 讀通行碼存 localStorage szgM_t 後清掉網址；API 用 X-Hub-Token，全身照 <img> 用 ?token=。401 → 顯示「請掃 QR 配對」。
  - 資料：GET /api/m/summary（`mobileSummary`：精簡角色＋未同步的帳號角色、近 3 小時工作、boss {mode, live}、parties（帶 `boardSellOf` 自動販售範本）、idleLog、update）；GET /api/m/maps（[id, 名稱, 最低等級, 區域]＋bosses 清單，給換圖與打王 fallback）。
  - 手機頁面：角色（需要處理、A/B/有狀況、搜尋、點卡片 → 底部面板：開始／暫停／重新開始／領取離線／換圖（依等級篩選的地圖清單）／切換為目前角色；「多選」→ 底部操作列）、工作（確認／取消／重試／刪除、全部確認、清除）、打王（模式、即時血條、每隻勾王 chips、全部／等級內／清除，存 /api/settings boss＝/api/boss cfg＋patch）、組隊（隊伍卡片、已就位／要套用、套用／全部套用）、更多（版本、開電腦版面板 /?token=裝置通行碼、登出、掛機紀錄）。每 10 秒更新（前景時）。
  - 測試 `tests/e2e_mobile.py`（extra_http_headers X-Forwarded-For 模擬經 serve 轉送）。
  - 還沒做：推播（使用者說先不用）、手機上編輯隊伍成員、市場／公倉。
- v0.52.1：使用者電腦是 REMOTE=1（start-remote.bat）、Tailscale 有機器名稱但沒設定 serve（https://機器名/m 連不到，http://100.x:8787/m 可以）。/api/m/info 多 serve（`tailscale serve status --json` 有沒有這個埠）；預設網址：有 serve 用 https 機器名，否則遠端模式用 http://100.x:埠。
- v0.52.2：使用者「加到主畫面後顯示還沒配對」——iPhone 主畫面 App 的 localStorage 和 Safari 分開，舊版讀完 #t= 就清掉網址、manifest start_url 也是 /m。改成：網址一直保留 `/m#t=通行碼`；manifest 由 JS 動態加 `<link rel=manifest href=/m/manifest.webmanifest?t=通行碼>`，伺服器回 start_url `/m#t=…`（只接受 16～64 位 hex）；沒配對畫面可以貼上網址（#pairIn）。
- v0.53.0 手機版上公開版（使用者：「可以連線，把教學跟版本放到公開版」）：拿掉 `<private:mobile>` 標記；make-public 改成只 cut 遠端版腳本（remoteUserscript）那段，保留 isLocal／tokenOk（公開版 tokenOk 只認配對過的手機，沒有共用 TOKEN）、gate、os、X-Hub-Token CORS 標頭、面板 ?token=；/api/m/info 的 remote 固定 false；禁用字只檢查 REMOTE、TOKEN、remote.user.js、remoteUserscript。公開版必須用 tailscale serve（伺服器只聽 127.0.0.1）；面板沒偵測到 serve 會提醒做第 2 步。兩邊 README 加「手機版」教學（Tailscale 官方文件核對：serve 需要 MagicDNS＋HTTPS Certificates，`--bg` 重開機後仍有效，`tailscale serve reset` 關掉）。用 SZG_REPO=公開版資料夾 跑過 e2e_mobile、e2e_smoke。
- v0.53.1：使用者要公開版步驟更詳細、連到 GitHub 讓人自己看或給 AI 協助安裝 → 公開版 repo 新增 `docs/mobile.md`（只在公開版 repo，make-public 不會動它；內容：運作方式、準備、6 個步驟含 Windows/macOS 指令與預期輸出、日常使用、安全、疑難排解表、關閉方法、給 AI 助手的說明）。公開版 README 手機版一節改成簡要流程＋連結；私人版 README、面板「📱 手機」都連到 https://github.com/Arashi9910/szg-hub-public/blob/main/docs/mobile.md。
- v0.54.0 手機版：POST /api/jobs/retry-all（failed→approved，log「重試全部」），手機工作分頁「全部重試（N）」；/api/m/summary 角色多 xp、nextXp、nextXpExact，summary 多 expTable；m.html 複製電腦面板的 ORIG_EXP／expNeed／lvTime（速度用遊戲整輪平均 hourly，沒有才用近 3 分），卡片「⏱ 升級 X・到 LvN Y（估）」、目標 Lv（localStorage szgM_tgt）、排序（szgM_sort：分頁／等級／升級最快／到目標最快／經驗最多），角色面板顯示還要多少經驗與預計達成時間。docs/mobile.md 日常使用表跟著更新。
- v0.54.1（公開版使用者回報：4 人隊打野王只有一隻去）：agent 快照的 party 以前是整包 {party, invites, accountParty} 超過 8000 字就變 {truncated:true}；真實遊戲 party 帶 messages（最多 40 則約 4.5KB）＋每個隊員約 20 個欄位（約 940 字），4 人隊必超過 → partyMap 看不到隊伍 → 只有勾的那隻單獨去。改成只送 party {code, leader, members:[{id,name,lv,job,map,auto,hp,maxhp,leader,self}]}、invites（數量）、accountParty。mock：MOCK_PARTY_MSGS（聊天＋隊員多餘欄位）、MOCK_MORE_ACCTS（A4 c5、A5 c6）。測試 `tests/e2e_boss_party4.py`（舊 agent 重現失敗、新版通過）。其他檢查過的情況：沒有自己分頁／沒在掛機／有其他工作的隊員會留下（紀錄會寫），屬設計行為。
- v0.54.2：使用者要求技能書併到消耗 → agent itemInfo 把 catalog 的 type『技能書』當『消耗』，面板 poll 時也把舊腳本回報的『技能書』改成消耗。遊戲有新地圖：當時 world 已經是 103 張圖、167 怪、1040 件裝備（和 /api/catalog 一致，11/22 自動上傳過）；為了內容改但數量不變也能更新，world 版本改成 'w6:…:' + FNV 雜湊（maps、mobs、drops、mapDrops、equipment、items、scrolls、autoSellDrops）；面板 `worldFreshCheck()` 每分鐘比 /api/world/version，不同就 loadWorld 並清 ptMapHtml／nameIdx／dexDropIdx／#mpTarget 快取。使用者說「目標或販賣單獨拉出來」那段先跳過。
- v0.55.0（使用者：技能書圖示要更新；打王要能「組隊一起打」或「保留組隊但各自分開打、不同時打同一隻」，全部刷完再回練功圖）：
  - 圖示：遊戲 catalog 的 items／scrolls／equipment 都有 icon（技能書在 /game/skill-books/<技能 id>.png、商店道具 /game/shop/item-<id>.png、/game/icons/…，裝備有些是 data: 圖）。world 多 `icons`（id → 路徑，只放和 /game/drops/<id>.png 不同、且不是 data: 的）；面板 itemImg 先用 WORLD.icons，再用冒險資料庫，最後 drops/<id>.png。
  - 打王設定 settings.boss.partyMode（'together' 預設｜'split'）、chain（預設 true）。server `bossUnitFor()`：split 時每隻自己一組（on 只看自己有沒有勾），共用的隊伍王靠 busyInst 避免同時去；面板總表 split 時不合併隊伍。
  - 連續打：agent runBossJob 改寫成 fightOne() 迴圈（最多 30 隻）：每打完一隻 fullSync＋postBossState、POST /api/boss/result，再 POST /api/boss/next {jobId, charId, prev(instanceId), mob}；server `bossNext()` 用和 bossTick 一樣的挑法（parts＝這一組正在打王的成員；別組正在打的 instance 不去；剛打完的那隻不去；30 分鐘內沒打成功的不去），決定存在 bossNextDec[隊伍或角色|prev]（3 分鐘），同隊的人拿到同一隻，並更新 job.batches[0].boss。沒有下一隻 → 回原本的地圖（第一隻就在冷卻、沒出發的不動），最後用 /api/boss/result {logOnly:true} 記「沒有下一隻了，回練功圖…（這一輪連續打了 N 隻）」。倒下、被換圖、出錯就不再連續。KIND_MIN_AGENT.boss → 0.55.0。
  - 面板：#bossPartyMode、#bossChain（設定抽屜）；手機打王分頁 #bPartyMode、#bChain。
  - 測試 `tests/e2e_boss_chain.py`（分開打不同隻、單隻連續打 2 隻後回家、隊伍一起連續打同一隻；測試裡直接 POST /api/boss/state 讓中控知道王已重生，不用等 4 分鐘回報）。
- v0.55.1：world 加了 icons 欄位但版本字串（內容雜湊）沒變 → 分頁不會重新上傳；版本前綴改 w7。之後 world 多加欄位都要改前綴。
- v0.56.0（使用者：「應該會有人要前面幾隻分開打、後面的王一起打」）：partyMode 多 'mixed'，settings.boss.togetherMobs＝一起打的王。bossTick 拆成 `bossPick(ids, c, now, busyInst, mobOk, dpsIds, stateIds)`＋`bossDispatch()`；mixed 且有隊伍時：隊員（有勾的、空閒的）各自挑「不在 togetherMobs」的王出發；這一輪有人出發或隊伍裡還有人在打王就跳過，否則整隊挑 togetherMobs 的王一起去。bossNext 在 mixed 時依工作的 boss.unit 決定：有隊伍代碼＝只接一起打的王、沒有＝只接分開打的王。修正兩個問題：① 自己打時王的狀態要用整個隊伍最新的一份（隊伍的王共用，隊友剛打死的才看得到冷卻）；② bossNextDec 的 key 改成（隊伍代碼＋工作 createdAt｜自己打用工作 id）＋prev，以前會拿到上一輪留下的決定。面板 #bossTogBox（勾選＋「Lv X 以上一起打」）、手機 #bTog。e2e_boss_chain 第 4 段測 mixed。
- 2026-11-23 圖文教學：公開版 repo `docs/guide.md`（安裝 Node.js → 下載 ZIP → start.bat → Chrome 設定檔 → Tampermonkey＋允許使用者指令碼（Chrome 138+，FAQ Q209）→ 安裝腳本 → 更新間隔「總是」→ 開遊戲確認「中控：已連線」→ 面板與各分頁教學 → 自動更新 → 常見問題 → 給 AI 助手的說明），截圖在 `docs/images/guide/`，用 `tests/guide_shots.py`（模擬環境、MOCK_APPEARANCE、MOCK_MORE_ACCTS、MOCK_PARTY；`SZG_REPO=公開版建置資料夾` 跑）重新產生；遊戲連線那張是裁切右下角提示。兩邊 README 都連到教學。Chrome／Tampermonkey 自己的畫面沒有截圖（無法在測試環境安裝擴充功能），用文字＋官方 FAQ 連結。
- v0.57.0 背景執行（使用者：不開 Chrome 也能跑，中控開著、能下指令就好；選了架構 A＝無頭 Chrome 的 MVP；遊戲用 Google 登入、電腦開著）：
  - `bg.js`（server.js `makeBg()`，零套件：Node 22 內建 WebSocket 走 Chrome DevTools Protocol）：每個背景帳號 settings.bg.profiles[] = {id, name, on, pages:[角色id|''], code, charIds}，Chrome 資料夾 `data/bg/<id>`（Default/Preferences 預先寫 restore_on_startup=1，避免遊戲登入 cookie 是工作階段 cookie 時關視窗就掉）。背景：`--headless=new --remote-debugging-port=0`，讀 DevToolsActivePort；每頁 Target.createTarget＋attach(flatten)→ Runtime.addBinding `__szgGmx`（GM_xmlhttpRequest 由 node 代送，只准連中控 origin）＋Emulation.setFocusEmulationEnabled＋Page.addScriptToEvaluateOnNewDocument（shim＋agentSource()＋userscriptSource() 本體，HUB 換成 http://127.0.0.1:PORT；`window.__szgBg={profile,key,standby}`，已注入就 return 防重複）→ navigate `/game/?szgChar=`。GM 值存 localStorage `__gm:`（同設定檔分頁共用，和 harness 一樣）。
  - 登入：同資料夾開**一般的 Chrome 視窗**（不接 DevTools，Google 登入不會被當成自動化）；使用者關視窗→exit 事件→on 的話自動 start。「登入完成」：有 DevTools 就 Browser.close，Windows 用 taskkill（不加 /F，正常關閉），其他 SIGTERM。**強制結束會遺失 cookie**（實測 SIGTERM 的無頭 Chromium 沒存 cookie、Browser.close 有）。測試用 SZG_BG_LOGIN_HEADLESS=1（無頭＋DevTools）、SZG_BG_LOGIN_PATH、SZG_BG_GAME（指到 mock）、SZG_CHROME、SZG_BG_TICK_MS。
  - 監看（每 15 秒 tick）：Chrome 斷線就重開（10 分鐘失敗 3 次停止自動重開）；分頁補開／關多的；probe 每頁（網址、mapleCharacter、__szgBg、徽章文字），每 60 秒 fetch /api/account（401/403 或 30 秒後還不在 /game → needLogin；學到 code、charIds 寫回設定）；分頁當掉或 3 次沒回應就重開；分頁 JS 錯誤記 r.logs（面板「分頁錯誤紀錄」）。
  - 中控重啟：DevToolsActivePort 還連得上就**接回**（不重開 Chrome、不重新整理：重新 attach、addBinding、addScript；`__szgBg.key` 對回分頁）。自動更新 exit 3 不關背景 Chrome；SIGINT/SIGTERM/SIGHUP/SIGBREAK（server.js 新增）先存檔、bg.shutdown() 關掉背景 Chrome 再結束。
  - 讓位：agent `BG`／`bgStandby`（passive() 也看它）、輪詢帶 `&bg=1`；背景頁每 15 秒 GET /api/bg/standby。server `realTabFor(code, charId, page)`＝這隻有新鮮的非背景分頁；/api/agent、/api/agent/beat 遇到就回 standby 且不 seenTab；tabs 多 bg 旗標（/api/data.tabs[].bg，總覽顯示「（背景執行）」）。
  - API（只限本機）：GET /api/bg；POST /api/bg/{config,add,rename,remove,start,stop,login,login-done,reload,pages}。移除不刪資料夾（確認框會寫路徑）。
  - 面板：header「🖥 背景」(#bgBox/#bgSum/#bgPop，開著時每 3 秒更新、平常 20 秒更新摘要「執行中/啟用數」)，每個帳號卡片：狀態燈、登入／登入完成、開始／停止、重新整理分頁、改名、移除，角色清單 `label.bg-ch`（點整列勾選，超過 2 隻 confirm），分頁狀態（執行中／暫停：你的 Chrome 開著／載入中）。
  - mock：MOCK_REQUIRE_LOGIN=1（沒 acct cookie 也沒 x-acct ＝ 401／「請先登入」頁）、`/__mock/login?acct=` 設 cookie 導回 /game/。測試 `tests/e2e_bg.py`（登入→背景→指令→第二隻→面板點整列→讓位與接手→中控重啟接回→停止）。
  - 公開版也有（bg.js 加進 make-public FILES 與 version.json files）。
- v0.58.0 帳號分頁（使用者：要大量填帳號開背景，要一個分頁管理、匯入匯出、自動登入 Google、帳號和總覽都能自己排序、點角色跳出那隻的頁面）。決定（AskUserQuestion，全選建議）：①**半自動批次登入、不存密碼**（全自動代填會被 Google 擋、可能鎖帳號、密碼外洩風險）②點角色＝背景改成看得到的視窗、腳本照跑 ③CSV ④總覽拖曳自訂順序並記住。
  - bg.js：profile 多 email、note；action edit／order／all（依序開始停止）／login-batch／login-skip／login-cancel（batch = {queue, cur, done, skipped}，登入視窗 exit 後 2.5 秒換下一個）／import（{csv, dry}；依 Email→名稱對應，順序照檔案，沒列到的保留在最後；匯出 CSV 有 BOM、公式字元前加 ' 防注入）／show {id, char}（stopBrowser 後 start(id, {visible})：不加 --headless、--new-window，activateTarget 那隻的分頁；r.visible）／hide。GET /api/bg/export.csv。第一次登入（沒有 code）且有 Email：登入視窗多開 `https://accounts.google.com/ServiceLogin?Email=…&continue=https://accounts.google.com/`。boot 改依序開。
  - 修正：中控自己關 Chrome（stopBrowser：登入、切顯示、停止）時 __closed 被算成當掉＋fails，連三次後停止自動重開 → r.stopping 旗標；onEvent 帶 cdp，舊連線的 __closed 不影響新連線（start 後舊的 close 事件晚到會把 r.cdp 清掉）。接回時用 Browser.getVersion 的 userAgent 判斷是不是看得到的視窗。
  - 面板：nav「帳號」(#accts)，header「🖥 背景」改成按鈕（#bgSum）帶到分頁；表格 tr.pickrow data-acpick（PICK_ATTRS 加 data-acpick）、⠿ data-drag（mousedown 才設 draggable，HTML5 DnD，拖曳中 ui.dragging 不重畫），input.ac-ed data-acf=name/email/note（change 存），角色小卡 .ac-ch（勾＝pages、名字按鈕 data-acshow＝顯示視窗），#acBatch 批次登入列（📋 複製 Email）。總覽 #ovCustom／#ovFromAcct、ui.ovSort 存 localStorage ovSort、key 'custom' 用 settings.ovOrder，列多 data-ovrow 與 ⠿。
  - 測試 e2e_bg.py 多 4b～4e（Xvfb :99 跑看得到的視窗；SZG_BG_LOGIN_PATH 支援 {name}）。
- v0.58.1（2026-11-23 22:30 用 Claude in Chrome 看使用者實機）：12 個背景帳號、24 個分頁全部 running、資料 30 秒內、全部在掛機（使用者 Node v26、Chrome 在 C:\Program Files）。使用者看到的「錯誤紀錄」是遊戲 game.js 自己的 `client error during sync AbortError`（遊戲同步逾時、會重試）14 筆＋agent `hub timeout` 1 筆。bg.js 錯誤紀錄改成只記 console 訊息含 szg-hub／中控的，例外則排除 AbortError 類。帳號表格在使用者螢幕上太寬（操作欄要左右捲），之後可以再壓縮。
- v0.59.0 更新公告（使用者：每次更新說明做了什麼，新功能簡單說明做什麼、怎麼用，留最近 5 次）：version.json `changelog`；GET /api/changelog（過濾 private、最多 5 筆）；面板 header「📢 更新」(#newsBtn，#newsDot 沒看過的新版亮紅點)＋#newsDrawer；localStorage newsSeen；新版第一次打開面板自動跳一次（navigator.webdriver 時不跳，免得擋住測試的點擊）；面板開著時 DATA.scriptVersion 變了就重抓。make-public 過濾 private、套 xxxPublic、檢查第一筆版本。e2e_smoke 多檢查公告。手機版還沒有公告。
- v0.59.1（使用者：自動上架、知識王跳錯誤）：用 Claude in Chrome 查，市場紀錄「自動上架出錯：hub timeout」與知識王「自動作答出錯：hub timeout」都集中在 22:32、22:42＝中控自動更新到 0.58.1、0.59.0 重新啟動的那幾秒（24 個背景分頁＋平常分頁同時在問）；中控平常 /api/data 約 15ms。agent 加 `hubDown(e)`（hub timeout／offline／5xx），自動上架、知識王、領收益、自動復活、裝備自動處理遇到就不記錯誤。另外看到有角色一小時內死 3 次（自動復活），沒處理，只提醒使用者。
- v0.60.0 背包條列（使用者：條列不能 Shift 多選、要顯示多一點）：data-bpick 的點選加 Shift 範圍（ui.bagLast，同容器 :scope > [data-bpick] 的兄弟，條列和格子都適用，結果跟這一列點下去一樣＝選或取消），Shift 時 mousedown preventDefault 不反白；表頭 #bListAll 全選／取消畫面上的列（ui.bagListShown）；ui.bag.listLimit 預設 1000，[data-blmore] 再顯示 1000／全部。e2e_filters 有測。
- v0.60.1（使用者轉述：「帳號目前的角色」不該能勾，登入後要變成帳號的兩隻；那邊跳錯誤時整個版面變很寬）：bg.js probe 學到 charIds 時，pages 有 '' 就換成「'_' 那頁目前顯示的角色＋帳號其他角色」（最多 2，或原本明確勾的數量），`rekeyPage()` 把 '_' 分頁改成那隻的 key（removeScriptToEvaluateOnNewDocument 舊的、加新的、改 window.__szgBg.key），不重開。setupSession 回傳 scriptId 存在 pg.scriptId。action pages：有 charIds 時只收帳號的角色、全部取消回錯誤（請按停止）。面板：有 charIds 就不顯示「帳號目前的角色」；狀態欄 .ac-st max-width 230px、td overflow-wrap:anywhere、.ac-chars max-width 380px。
