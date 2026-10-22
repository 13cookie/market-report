# 每日市場晨報(幣圈 + 台股)→ LINE 自動推送

每天台灣時間早上約 7:30,自動抓取 BTC/ETH 行情、台股加權指數,以及中英文市場新聞,交由 Claude API 產生 500 字以內的繁體中文分析,透過 LINE 官方帳號推送到你的 LINE。

> ⚠️ 報告為 AI 自動彙整之市場觀察,僅供參考,不構成投資建議。

## 專案結構

```
market-report/
├── main.py                          # 主程式
├── requirements.txt                 # 套件清單
├── LICENSE                          # MIT 授權
└── .github/workflows/daily_report.yml  # GitHub Actions 排程
```

## 部署步驟(約 15 分鐘)

### 1. Fork 本專案

點本頁右上角 **Fork**,複製一份到你自己的 GitHub 帳號(公開或私人都可以)。

> 金鑰一律存在 GitHub Secrets,不會寫進程式碼,Fork 也不會帶走原作者的 Secrets,所以公開 repo 也安全。

Fork 之後到你的 repo → **Actions** 分頁 → 按「I understand my workflows, go ahead and enable them」啟用排程。

### 2. 取得三把鑰匙

| Secret 名稱 | 取得方式 |
|---|---|
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Developers Console → 你的 Provider → Messaging API Channel → **Messaging API** 分頁 → Channel access token → Issue |
| `LINE_USER_ID` | 同一個 Channel → **Basic settings** 分頁 → 最下方 **Your user ID**(U 開頭的字串) |
| `ANTHROPIC_API_KEY` | https://console.anthropic.com → API Keys → Create Key(需綁付款方式;此排程每天一次,費用極低) |

**重要:** 你的 LINE 個人帳號必須先把這個官方帳號**加為好友**,官方帳號才推得了訊息給你。

### 3. 設定 GitHub Secrets

Repo 頁面 → Settings → Secrets and variables → **Actions** → New repository secret,依上表名稱逐一新增三個 Secret(名稱必須完全一致)。

### 4. 手動測試

Repo → **Actions** 分頁 → 左側選「Daily Market Report」→ 右側 **Run workflow** → Run。約 1-2 分鐘後你的 LINE 應該會收到晨報;若失敗,點進該次執行看紅字錯誤訊息。

### 5. 完成

之後每天 UTC 23:23(台灣 07:23)自動執行。GitHub 排程尖峰時可能延遲 5-15 分鐘,屬正常現象。

## 常見調整

- **換新聞來源**:編輯 `main.py` 上方的 `CRYPTO_FEEDS` / `TAIWAN_FEEDS`,任何 RSS 網址都能加;來源掛掉會自動略過。
- **調整報告長度/風格**:修改 `analyze_with_claude()` 內的 prompt。
- **改推送時間**:修改 `daily_report.yml` 的 cron(注意是 UTC,台灣時間要減 8 小時)。
- **加個股追蹤**:之後想加個股,告訴 Claude 幫你擴充即可。

## 疑難排解

- **LINE 收不到**:確認已加官方帳號好友;確認 `LINE_USER_ID` 是 Basic settings 的 Your user ID,不是 LINE ID;免費方案每月推送則數有上限(個人使用綽綽有餘)。
- **Actions 沒自動跑**:Repo 若 60 天無任何活動,GitHub 會暫停排程,到 Actions 頁按 Enable 即可恢復;偶爾 commit 一下也可避免。
- **Claude API 錯誤 401/403**:API Key 貼錯或帳戶未儲值。

## 授權

[MIT](LICENSE)。歡迎 Fork、修改、發 Issue 或 PR。
