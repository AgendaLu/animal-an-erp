# 測試策略 — Animal-AN ERP v0.4

> 2026-07-04 制定。涵蓋會計模組(ORM / ViewModel / REST API)與部署基礎設施。
> 執行方式:`.venv/bin/python -m pytest`(設定見 pyproject.toml `[tool.pytest.ini_options]`)

## 測試金字塔與現況

| 層級 | 範圍 | 現況(制定前) | 目標 |
|---|---|---|---|
| 單元測試 | ORM 計算欄位、約束、VM 業務規則、工具函式 | ✅ 42 個(models/VM/inventory) | 維持,補金額捨入邊界 |
| 整合測試 | REST API(FastAPI TestClient + 暫存 DB)、CSV 匯入、migration、備份 | ⚠️ 僅 11 個(DB init/backup/1 個匯入) | **本次補齊重點** |
| E2E | 瀏覽器操作前端 SPA | ❌ 無 | 暫緩(前端為單檔 SPA,先以 API 整合測試守住) |

## 各區塊測什麼

### 1. 會計 ORM(models/accounting.py)— 單元測試 ✅ 已覆蓋
- 行金額/稅額/毛利計算、發票彙總、付款狀態轉移(UNPAID→PARTIAL→PAID)
- 唯一約束:發票號碼、供應商+號碼、稅期+稅別
- AR/AP 逾期天數計算(已付清不算逾期)
- **缺口→補**:金額捨入邊界(Float 存金額為已知風險,round-half-even 行為需釘住)

### 2. AccountingViewModel — 單元測試 ✅ 已覆蓋
- 開發票同步建 AR/AP、收付款核銷、超額付款拒絕
- 日報表、月稅務彙總(save/upsert/已申報鎖定)、AR/AP 清單過濾

### 3. REST API(web/app.py)— 整合測試 ❌ 零覆蓋 → **P0**
測試基礎:`TestClient` + monkeypatch `web.app.DB_PATH` 指向 tmp_path,避免碰到 `data/animal_an.db` 正式資料庫(startup 事件會 init 該路徑)。

| 端點群 | 案例 |
|---|---|
| 會計發票 POST | 成功(ISO 日期字串解析、回傳合計)、空明細 400、重複發票號(目前 500,期望 4xx → xfail 記錄) |
| 收付款 POST | 部分→全額核銷後 receivables 反映、超額 400、缺 amount 400、發票不存在 400 |
| 報表 GET | daily-sales 合計、tax save=true upsert、已申報(FILED)後 save 400、無效日期(目前 500 → xfail) |
| AR/AP GET | outstanding_only 切換 |
| 通用 CRUD | 建立/清單/更新、缺 code/name 400、未知 entity 404、不存在 id 404、enum 序列化往返 |
| 進銷存流程 | 供應商→原物料→進貨單(收貨入庫)→分裝→銷貨(FEFO)→估值/低庫存/近效期;單號序列 PO/SO-001、002;缺欄位 400、超發 400、負庫存調整 400 |

### 4. 部署基礎設施 — 整合測試 ⚠️ 部分覆蓋 → **P1**
| 模組 | 案例 |
|---|---|
| config/environments.py | 三環境參數正確(testing: port 8001/:memory:/關備份;production: 0.0.0.0/開備份)、未知環境 ValueError、預設 DB 路徑補齊、ANIMAL_AN_ENV 偵測與非法值 fallback |
| scripts/migrate_v03.py | 舊 schema DB 加欄位、customer_type 舊值映射(Veterinary→VET_CLINIC、未知→NULL)、migration 前自動備份、重跑冪等、缺表跳過不炸 |
| scripts/import_data.py | customers/products/materials 匯入、重跑冪等(跳過重複)、壞 enum 記錄錯誤且不中斷其他列、日期/浮點/布林解析器、空 CSV 不炸 |
| utils/backup.py | CLI 參數錯誤路徑(無參數/未知指令/restore 缺檔名 → exit 1)、format_size、還原不存在檔案 False、來源 DB 不存在 None(核心備份/還原/清理已有測試) |

### 5. 明確不測
- views/(PyQt5 桌面版,gui extra 未安裝)、web/app.py 內嵌 HTML/JS 字串、`__repr__`、logger、Docker build(屬 CI 範疇)

## 覆蓋目標
- models/accounting.py、viewmodels/accounting_vm.py:≥ 90% 行覆蓋
- web/app.py API 路由(排除 PAGE 字串):≥ 80%
- scripts/、config/、utils/backup.py:≥ 70%
- 全案(排除 views/、build/):≥ 75%

## 測試設計原則
1. 每個測試用獨立 tmp_path DB;`DatabaseManager` 是 singleton,fixture 內重新 `init_db` 即隔離
2. **絕不**讓測試觸碰 `data/animal_an.db`:API 測試一律 monkeypatch `DB_PATH`;不在既有舊 DB 上呼叫 `init_db`(會觸發 subprocess migration 打到正式資料目錄 — 見下方已知風險 #2)
3. 已發現但不在本次修的 bug:以 `xfail(strict=False)` 釘住期望行為,修好後轉 XPASS 可見

## 已知風險(測試過程盤點)
1. **金額用 Float**:accounting_database_design 已標註;長期應改 `Numeric(12,2)`/整數分 — 待修
2. ~~`DatabaseManager._run_migrations` 路徑寫死~~ — **已修**(改為 in-process `migrate(self.db_path)`,分支 claude/awesome-diffie-ed9577,含回歸測試)
3. **API 錯誤處理缺口**(重複發票號/無效日期/未知欄位 → 500):應皆回 4xx — 待修
4. **CSV `_parse_float` 把逗號當小數點**:`1,234.56`(千分位)會解析失敗回 0.0,台灣報表常見格式,匯入金額歸零風險 — 待修

## 2026-07-04 增補(報表與打包)
- **tests/test_reports.py**:ReportViewModel 單元(月報分桶/快照告警/毛利分組/分裝守恆/信用超額)+ /api/reports/* 整合與 400 驗證
- **tests/conftest.py**:client fixture 共用(暫存 DB 隔離)
- **DB 路徑決議測試**:env 覆寫 / frozen 執行檔同層 / 開發預設三分支
- 打包驗收:PyInstaller onedir 建置後,實測啟動、HTTP 200、DB 落點、防重複啟動
