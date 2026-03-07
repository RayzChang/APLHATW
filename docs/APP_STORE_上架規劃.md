# 台股交易推手 — App Store 上架規劃

## 技術選型

| 方案 | 優點 | 缺點 |
|------|------|------|
| **React Native + Expo** | 跨平台、熱更新、與 Web 共用邏輯 | 需學習 RN |
| **Flutter** | 效能佳、UI 一致 | 需 Dart、與現有 Web 不同棧 |
| **PWA** | 無需上架、即時更新 | 功能受限、無法上架 App Store 主列表 |
| **Capacitor + React** | 用現有 React 包成 App | 需維護 Web + App |

**建議：React Native + Expo**
- 與加密貨幣交易推手前端技術棧可共用
- Expo 簡化建置與 OTA 更新
- 可先做 Web，再包成 App

---

## 上架前檢查清單

### 1. Apple App Store 要求
- [ ] Apple Developer 帳號（年費 $99 USD）
- [ ] 隱私權政策 URL
- [ ] 使用條款
- [ ] 金融/投資類 App 需說明「不構成投資建議」
- [ ] 無實盤下單功能（模擬交易可）

### 2. 功能範圍
- ✅ 選股器（技術指標篩選）
- ✅ 策略回測
- ✅ 模擬交易
- ⚠️ AI 分析：需注意 API 使用條款（Gemini 等）
- ❌ 實盤下單：需券商合作或金管會核准

### 3. 實作步驟
1. **Phase 1**：完成 Web 版（目前進度）
2. **Phase 2**：用 Expo 建立 React Native 專案
3. **Phase 3**：將 API 呼叫、狀態管理抽成共用模組
4. **Phase 4**：App UI 適配（手機版選股、K 線圖）
5. **Phase 5**：TestFlight 內測
6. **Phase 6**：提交 App Store 審核

---

## 目錄結構建議

```
mobile/
├── app/           # Expo Router 頁面
├── components/     # 共用元件
├── api/           # API 客戶端（與 Web 共用邏輯）
├── app.json       # Expo 設定
└── package.json
```

---

## 注意事項
- 投資類 App 審核較嚴，需明確標示風險
- 模擬交易需註明「非真實資金」
- 建議先以 Web 版驗證產品，再投入 App 開發
