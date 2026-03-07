<div align="center">

# 📈 台股交易推手

### _Taiwan Stock AI Trading Assistant_

**上市 · 上櫃 · 台指期 — 全市場覆蓋**

> 技術指標選股 × AI 分析 × 模擬交易 × 策略回測
>
> **目標：100 萬台幣 × 一週模擬交易成效驗證**

---

![](https://img.shields.io/badge/版本-v1.0-blue?style=for-the-badge)
![](https://img.shields.io/badge/引擎-Python_3.11-blue?style=for-the-badge)
![](https://img.shields.io/badge/前端-React_+_Vite-cyan?style=for-the-badge)
![](https://img.shields.io/badge/市場-上市+上櫃+台指期-green?style=for-the-badge)

</div>

---

## 🎯 核心價值

**實盤前先驗證 — 拿真錢上場前，先確保系統穩固**

| 功能 | 說明 |
|------|------|
| 🔍 **智慧選股** | 使用者有興趣的幾家公司，AI 撈取**資訊面**（本益比、營收）、**技術面**（KD、RSI、MACD）、**籌碼面**（三大法人、融資融券），供使用者衡量是否可買。決策由使用者自己做。 |
| 💰 **模擬交易** | 使用者放一筆資金，**AI 自主決定**交易哪些標的（上市、上櫃、期貨都可能）。使用者不選股，由 AI 掃描全市場。一週或一個月後看成效。 |
| 🚀 **最終目標** | 串接券商 API 做程式/AI 交易 |

---

## 📋 資料來源

- **上市股票**：證交所 / FinMind
- **上櫃股票**：櫃買中心 / FinMind  
- **台指期**：期交所 / FinMind
- **更新時間**：每日 16:00 後更新當天數據

---

## 🚀 快速開始

```bash
# 1. 建立虛擬環境
python -m venv venv
venv\Scripts\activate   # Windows

# 2. 安裝依賴
pip install -r requirements.txt

# 3. 設定環境變數
copy .env.example .env
# 編輯 .env 填入 FINMIND_TOKEN（必填，否則無法取得行情與加權指數）至 https://finmindtrade.com/ 免費申請

# 4. 啟動
python launcher.py
```

---

## 專案結構

```
├── launcher.py              # 控制台啟動器
├── main.py                  # 交易引擎入口
├── config/                  # 設定
├── core/
│   ├── data/                # 台股資料來源（上市/上櫃/台指期）
│   ├── analysis/            # 技術分析引擎
│   ├── strategy/             # 交易策略
│   ├── execution/            # 模擬交易執行
│   └── risk/                # 風險管理
├── api/                     # FastAPI 後端
├── frontend/                # React 儀表板
├── mobile/                  # App 上架用（React Native / Expo）
└── scripts/                 # 模擬交易測試腳本
```

---

## ⚠️ 免責聲明

本平台僅供模擬交易學習用途，不構成任何投資建議。投資有風險，請謹慎評估。

---

**Made with ❤️ — 台股交易推手**

</div>
