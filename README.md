# 好市多特價推播

每天自動檢查好市多台灣官網的特價商品，出現新一期特價時推播到 Discord，並產生可搜尋、篩選的完整彙整報表。

## 功能

- **新上架特價摘要**：新增筆數、檔期、分類統計、折扣幅度排行。
- **區分通路**：網路獨家 🌐、線上賣場同價 🏬、一般線上特價，以及賣場（現場）特價。
- **關注清單**：商品名稱命中關鍵字時，逐項附圖單獨通知。
- **歷史低價標記**：長期記錄每項商品的特價價格，創新低時標記 🔥。
- **完整報表**：單一 HTML 檔，可搜尋、依分類／通路篩選、依折扣或截止日排序。

沒有新特價時不會推播。

## 設定步驟

### 1. 建立 Discord Webhook

在要接收通知的頻道：**編輯頻道 → 整合 → Webhook → 新 Webhook → 複製 Webhook 網址**。

### 2. 設定 GitHub Secret

Repo 的 **Settings → Secrets and variables → Actions → New repository secret**：

| 名稱 | 值 |
|---|---|
| `DISCORD_WEBHOOK_URL` | 上一步複製的 Webhook 網址 |

### 3. 啟動排程

**Actions → 好市多特價推播 → Run workflow** 手動執行第一次。第一次會把目前所有特價彙整後推播一次，之後只在有新特價時推播。

排程為每天台灣時間 08:30 與 18:30（GitHub 的排程可能延遲數分鐘到數十分鐘），可在 `.github/workflows/costco-deals.yml` 調整。

### 4.（選用）用 GitHub Pages 線上瀏覽報表

報表每次都會以附件送到 Discord。若想要直接點連結瀏覽：

1. **Settings → Pages → Source** 選 `Deploy from a branch`，分支 `main`、資料夾 `/docs`。
2. **Settings → Secrets and variables → Actions → Variables** 新增 `REPORT_URL`，值為 Pages 網址（例如 `https://<帳號>.github.io/CostcoOnSell/`）。

免費方案的 GitHub Pages 需要公開的 repo。

## 調整設定

編輯 `config.toml`：

| 設定 | 說明 |
|---|---|
| `watchlist` | 關注關鍵字，比對商品中英文名稱，不分大小寫 |
| `top_n` | 折扣幅度排行顯示幾項 |
| `max_watch_hits` | 單次最多逐項顯示幾個關注清單命中 |
| `attach_report` | 是否把 HTML 報表附在 Discord 訊息 |

## 本機執行

需要 Python 3.11 以上，不需安裝任何套件。

```bash
python -m costco_deals --dry-run     # 只預覽：結果輸出到 out/，不推播、不寫入狀態
python -m costco_deals --test-push   # 送一則測試訊息確認 Webhook
python -m costco_deals               # 正式執行
python -m unittest discover -s tests # 執行測試
```

本機的 Webhook 網址放在 `.env`（參考 `.env.example`，此檔不會進版控）。

## 資料來源與限制

資料來自好市多線上購物官網（costco.com.tw）的公開商品介面。

- **線上特價**取自「優惠商品」分類，含原價、特價、折扣金額與期間。
- **賣場特價**取自「賣場獨家商品」分類中帶有優惠期間的商品。官網不公開賣場售價與折扣金額，
  且只涵蓋實體賣場優惠的一小部分，實際優惠以賣場標示為準。
- 多規格商品（服飾、鞋類等）在列表上沒有單一售價，只顯示折扣金額。
- 「歷史低價」只依本系統開始記錄後看到的特價價格判斷，剛啟用時沒有可比較的紀錄。
- 官網介面若改版或阻擋雲端主機連線，排程會失敗並在 Discord 發出失敗通知。

## 檔案結構

```
costco_deals/      程式（fetcher 擷取、store 狀態與歷史、notify 推播、report 報表）
config.toml        設定
data/state.json    已通知過的特價（由排程自動更新）
data/history.json  價格歷史（由排程自動更新）
docs/index.html    最新彙整報表（由排程自動更新）
```
