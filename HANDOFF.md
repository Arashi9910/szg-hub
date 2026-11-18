# 上漲谷中控：開發交接筆記（私人，不同步到公開版）

最後更新：2026-11-18（v0.29.2）

## 環境與流程
- 私人 repo：本 repo（含 Tailscale／遠端設定）。公開 repo：`Arashi9910/szg-hub-public`。
- 每次更新的固定流程：
  1. 改 `version.json` 版本號與 notes（新增檔案要加進 `files`）
  2. commit／push 私人 repo（作者 Claude，結尾加 Co-Authored-By 與 Claude-Session 兩行）
  3. `python3 tools/make-public.py <私人repo路徑> <公開repo路徑>` 產生公開版（會拿掉 REMOTE／TOKEN／Tailscale，新增的程式檔要加進 `tools/make-public.py` 的 FILES）
  4. 更新公開 repo 的 README（公開版 README 獨立維護），commit 後 `git -c push.negotiate=true push`
  5. 在使用者面板分頁（http://127.0.0.1:8787/）執行 `/api/update/check` → `/api/update/apply` 套用；遊戲分頁約 2 分鐘內自動換新腳本
- 測試：`tests/`（e2e_smoke、e2e_guild、e2e_guild_auto、e2e_switch、e2e_forge、e2e_guild_sell、e2e_agent_gate、e2e_bag_guild、e2e_board_group、e2e_view_group）；原本寫在 `/home/claude/test`（mockgame.js 模擬遊戲、harness.py 共用工具、e2e_smoke.py 冒煙測試，`python3 e2e_smoke.py`）。harness 會把私人 repo 複製到 /tmp/hub 當測試中控，並先 `POST /api/settings {"autoUpdate":false}`，否則會被 GitHub 版本蓋掉。2026-11-18 舊測試檔隨舊工作階段消失，已重寫；**之後要放進 repo 才不會再不見**。
- 使用者規則：每次更新私人版與公開版一起同步；公開版不要放個人資料與 Tailscale 設定；**公會倉庫相關功能只做私人版**（公開版其他人做法可能不同），之後用程式標記讓 make-public 移除。

- **新增工作種類時**：在 server.js 的 `KIND_MIN_AGENT` 登記最低腳本版本（私人種類寫在私人區塊裡），否則舊腳本的分頁會拿到工作然後「未知的工作類型」失敗。遊戲分頁有時會卡在舊腳本好幾版（Tampermonkey 快取），只能請使用者手動重新整理那個分頁。

## 檔案
- `server.js` 中控伺服器（工作佇列、掛機、市場、題庫、DPS、掉落紀錄 /api/loot 只放記憶體）
- `agent.js` 遊戲頁面腳本（由 `szg-hub.user.js` 載入；旁聽頁面 fetch 取 DPS 與掉落）
- `dashboard.html` 面板（單一檔案）
- `market.js` 市場行情／自動上架；`extdb.js` 外部「冒險資料庫」（題庫、圖示、道具說明，執行時下載）
- `update.js` 自動更新；`quiz-bank.json` 內建題庫

## 遊戲 API 重點（/api/game）
- 需要 `X-Game-Version` 標頭（頁面 fetch 會加）；非 sync 動作要 requestId；「存檔忙碌」要重試（agent 的 `gameRetry`）
- 換圖 `{type:'map', map, characterId}`；切換角色 `{type:'switch'}`。頁面重新載入時用 `sessionStorage.mapleCharacter` 決定角色，但**遊戲每次同步完會把它寫回畫面上的角色**（記憶體裡的 state），所以 agent 切換後要擋住這個寫入再立刻重新整理（v0.25.2）；伺服器的「目前角色」也會跟著頁面同步的角色走
- 自動販售 `{type:'autoSell', characterId, map, config:{enabled,itemIds}}`：**只接受角色目前所在地圖**
- 所有 /api/game 回應都是「整份狀態放最上層」（character、characters、tradeEligible…）＋ `summary`；頁面把它存成 `mapleSessionView = {state: 回應}`
- 批次衝卷（神匠之魂，2026-11-18 讀遊戲程式碼核對）：單件 `{type:'artisanScroll', uid, item, count(≤10), stopAfterSuccesses(0=不停), expectedSlots: g.slots, stopOnFail}`；多件把 `uid` 換成 `uids:[2～10]`。**每衝 1 次**扣 1 張卷軸＋10 萬楓幣（ARTISAN_FEE），失敗也扣格；卷軸要在同一隻角色身上，適用條件 `catalog.scrolls[id].target === gear.type`；詛咒卷軸失敗可能讓裝備消失。多件時遊戲要求**名稱、key、剩餘次數相同而且沒鎖定**。結果在 `character.lastArtisan`（單件 `{uid, attempts:[bool], successes, destroyed, slots, fee, stop}`；多件 `{multi:true, gear, selected, scroll, rate, items:[{attempts, successes, destroyed, slots, stop}], successes, lost, fee, stop}`；前者是讀遊戲程式碼推的，還沒實際衝過）。目錄 `catalog.scrolls[key] = {name, target, rate, cursed(失敗消失 %), stats}`。單次 `{type:'scroll', item, target, uid}`
- 公會倉庫（2026-11-18 實際存取 1 張卷軸核對）：`guildWarehouseView`、`guildWarehouseBatch {op:'deposit'|'withdraw', items:[{kind:'item', item:key, qty} | {kind:'gear', uid}](≤100), characterId}`。回應在 `summary.guildWarehouse = {guildName, mesos, cashPoints, items:{key:qty}, gear:[], capacity:{gear:500, items:500}, taxPercent:5}`；同步回應不會帶公倉內容。**單次請求另有伺服器上限**：98 種、10,658 張卷軸一次送會回「請求過大」（門檻不明，遊戲畫面只限 100 項），agent 會自動切半重送。楓幣／點數是另外的 `guildWarehouseMesos`、`guildWarehouseCash`（使用者規則：不要動楓幣）。鎖定裝備、任務道具、不可交易的不能存。公會名「佐藤商會」，11 個帳號都在裡面
- 戰鬥事件在 sync 回應 `summary.events`（actor、damage、effectiveDamage、lines、skill、mob、killed）；冒險紀錄 `character.log`（「撿取：X × n」「自動販售：X × n，獲得 N 楓幣」）
- 目錄 `/api/catalog`：maps、mobs、mapDrops、drops、autoSellDrops（每張圖可販售的掉落）、skills、fourth（4 轉技能書：level、fee、bookDrops、books；技能書在背包「消耗」分頁）
- 傷害測試稻草人地圖 gms990040001／gms990040002（單人，產生 character.dpsReport）

## 目前功能（面板分頁）
總覽（需要處理、實戰 DPS 欄與明細、批次掛機）、裝備（清單／對照／撿到自動處理、同名合併）、交易、背包（依道具／依角色、含倉庫、跨角色賣出／鎖定／給某角色）、派工（工廠圖＋清單、匯入目前設定、目標掉落估算、自動販售範本、掉落動畫）、地圖（查詢、換圖、練功效率提示、組隊試算用實戰 DPS）、市場、知識王。
- **公倉（v0.25，僅私人版）**：存入選單（全部角色背包可存的東西→勾選→裝備用掉落浮動條件篩選→每隻角色一個 `guildDeposit` 工作）；公倉內容（`/api/guild` 存最後一次看到的內容；↻ 重新整理建立 `guildView` 工作，只讀所以自動排隊）→勾選＋給誰→`guildWithdraw`。裝備的建議對象＝冒險資料庫的職業＋等級，等級剛好夠的排最前面（使用者選「只建議，自己選」）。存入設定記在 settings.guildDep（names＝個別勾選、cats＝整類「卷軸」「裝備」）。
- **公倉自動存入（v0.26）**：settings.guildAuto `{mode:'off'|'preview'|'deposit', everyMin}`，server 每分鐘檢查、到時間就照 guildDep 替在線的目前角色建 `guildDeposit`（auto:true、直接 approved）；剛做完公倉工作、還沒回報新資料的角色跳過；公倉快滿就停。紀錄在 db.guildLog，`POST /api/guild/auto-run` 立即執行。
- 私人功能用 `<private:名稱>` … `</private:名稱>` 整行標記包起來（JS `//`、HTML `<!-- -->`），make-public 會整段移除並檢查公倉字樣沒有外漏；version.json 的 `notesPublic` 會變成公開版的 notes。

- **派工分組（v0.29）**：settings.boards = {A, B}（舊的 settings.board 當 A），settings.charGroup 覆寫分組（預設帳號角色清單第 1 隻＝A）；`boardGroup()` 自動＝有兩隻角色的帳號中目前角色多的那組。saveBoard 要存「當下那一份」並在 boardPending 期間讓 poll 保留本機設定（v0.29.1 修過一次被 poll 蓋掉的 bug）。看板只顯示該組角色（含沒同步過的，用 accountChars 補），非目前角色＝背景掛機，套用時略過。v0.29.2 裝備、交易分頁共用檢視組別 `ui.vg`（localStorage viewGroup；`snapsV()`／`allGear(true)`／`wearers()` 只看該組）。使用者不想看到兩組混在一起。使用者玩法：切換角色後另一隻在背景掛機，偶爾收菜。

## 待辦（使用者已同意的方向）
1. 派工工廠圖持續依使用者回饋調整（操作手感、動畫）
2. ~~公會倉庫串接~~（v0.25 完成；v0.26 自動存入）。v0.26.1 工廠圖公倉節點（pos.guild、線 key `bag>guild`、`flyIcon()` 共用飛行動畫）。v0.28 公倉整理：裝備浮動篩選＋`guildSell` 工作（由某角色每批領出 50 件→inventoryQuote/Sell，遊戲不能直接從公倉賣）。2026-11-18 使用者把 11 隻角色背包的 361 件裝備全部存進公倉。v0.28.4 背包分頁「存進公倉」（公開版的擴充點 `bagExtraActions`／`bagActHooks`，私人區塊實作；存入直接 approve）。之後可加：依職業一鍵分配、公倉裝備同名合併檢視、不及格上架市場
3. ~~強化工坊~~（v0.27：「強化」分頁、`forge` 工作、`/api/forge` 結果；agent 用衝之前／之後的裝備狀態算每件結果，不依賴 lastArtisan 格式；私人版 `forgeExtra` 補上公倉來源，執行時先領出）。2026-11-18 使用者第一次實衝成功（18 件馬爾斯黑拳套、手套攻擊卷軸60%，+5×1 +4×6 +3×8 +2×3，900 萬），結果記錄正確；v0.28.3 結果顯示 +幾分布與增加素質
4. **分流**：及格→鎖定／給適合的角色；不及格→商店或市場自動上架
5. 之後：打技能書路線（4 轉，使用者進度未到）

## 使用者偏好
- 清單選取要「點整列」就能選（`tr.pickrow`＋勾選框的 data-*pick 屬性，共用點選／Shift 選一段的處理），不要只能點小勾選框
- 繁體中文；先給結論；介面要一眼看懂、操作直覺，喜歡有「自動工廠」感的視覺
- 會動到遊戲資料、金錢、不可逆的操作要先確認；藥水會自動買，不需要提醒
