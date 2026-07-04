# 部署指南 - Animal-AN ERP

完整的本機、Docker 容器化部署和運維指南。

## 📋 目錄

1. [快速開始](#快速開始)
2. [桌面版打包（PyInstaller）](#桌面版打包pyinstaller)
3. [本機部署](#本機部署)
4. [Docker 部署](#docker-部署)
5. [環境配置](#環境配置)
6. [資料庫備份和恢復](#資料庫備份和恢復)
7. [資料匯入](#資料匯入)
8. [故障排查](#故障排查)

---

## 桌面版打包（PyInstaller）

給非技術使用者的單資料夾版本：雙擊執行檔 → 自動起本機伺服器並開瀏覽器。

```bash
# macOS / Linux（在該平台上打包，不可交叉編譯）
scripts/build_desktop.sh

# Windows
scripts\build_desktop.bat
```

產物在 `dist/animal-an-erp/`：

| 項目 | 說明 |
|---|---|
| `animal-an-erp(.exe)` | 主執行檔，雙擊啟動；console 視窗保持開啟即代表系統執行中，關閉即停止 |
| `data/animal_an.db` | 資料庫（首次啟動自動建立）。**更新程式時整包換新、只保留 `data/`** |
| 環境變數 `ANIMAL_AN_DB` | 可覆寫資料庫路徑（例如放到共用磁碟） |

打包設定在 `packaging/animal_an.spec`（onedir、含 `web/static`、排除 PyQt5/tkinter）。
重複啟動保護：port 8000 已被占用時，新實例只開瀏覽器連到既有服務後退出。

---

## 快速開始

### Windows 用户（最简单）

```bash
# 1. 进入项目目录
cd animal-an-erp

# 2. 运行启动脚本
scripts\run_web.bat

# 3. 打开浏览器
http://127.0.0.1:8000/api/docs
```

### macOS / Linux 用戶

```bash
# 1. 進入項目目錄
cd animal-an-erp

# 2. 讓腳本可執行
chmod +x scripts/run_web.sh

# 3. 運行啟動腳本
./scripts/run_web.sh

# 4. 打開瀏覽器
http://127.0.0.1:8000/api/docs
```

---

## 本機部署

### 需求
- Python 3.9 或更新版本
- 磁碟空間：最少 500MB（包括虛擬環境）
- 網路：可選（應用完全離線運作）

### 安裝步驟

#### 1. 建立虛擬環境

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

#### 2. 安裝依賴

```bash
# 安裝所有依賴
pip install -e .

# 或僅安裝核心依賴
pip install -r requirements.txt
pip install uvicorn fastapi
```

#### 3. 初始化資料庫

```bash
# 自動初始化（在啟動腳本中完成）
# 或手動初始化
python -c "from models.database import db_manager; db_manager.init_db()"
```

#### 4. 啟動 Web 伺服器

```bash
# 開發模式（自動重載）
python -m uvicorn web.app:app --host 127.0.0.1 --port 8000 --reload

# 或使用啟動腳本
./scripts/run_web.sh          # macOS/Linux
scripts\run_web.bat           # Windows
```

#### 5. 訪問應用

- Web 應用：http://127.0.0.1:8000
- API 文檔：http://127.0.0.1:8000/api/docs
- API 互動：http://127.0.0.1:8000/api/redoc

### 多實例部署

要在同一台機器上運行多個實例，使用不同的埠：

```bash
# 實例 1（預設埠）
python -m uvicorn web.app:app --host 127.0.0.1 --port 8000

# 實例 2（不同埠）
python -m uvicorn web.app:app --host 127.0.0.1 --port 8001

# 實例 3
python -m uvicorn web.app:app --host 127.0.0.1 --port 8002
```

---

## Docker 部署

### 需求
- Docker 19.03 或更新版本
- Docker Compose 1.25 或更新版本
- 磁碟空間：最少 1GB

### 快速啟動

```bash
# 建立並啟動容器
docker-compose up -d

# 檢查狀態
docker-compose ps

# 查看日誌
docker-compose logs -f web

# 停止容器
docker-compose down
```

### 手動建立和運行

```bash
# 建立映像
docker build -t animal-an-erp:latest .

# 創建數據卷（首次）
docker volume create animal-an-db

# 運行容器
docker run -d \
  --name animal-an-web \
  -p 8000:8000 \
  -v animal-an-db:/app/data \
  -v $(pwd)/logs:/app/logs \
  -e ANIMAL_AN_ENV=production \
  animal-an-erp:latest

# 查看日誌
docker logs -f animal-an-web

# 停止容器
docker stop animal-an-web
```

### Docker 生產配置

#### 使用反向代理（nginx）

```nginx
upstream animal-an-erp {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name erp.example.com;

    location / {
        proxy_pass http://animal-an-erp;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### 持久化數據卷

```bash
# 創建具名卷
docker volume create animal-an-data
docker volume create animal-an-logs

# 在 docker-compose.yml 中使用
volumes:
  - animal-an-data:/app/data
  - animal-an-logs:/app/logs
```

---

## 環境配置

### 環境變數

```bash
# 設置環境
export ANIMAL_AN_ENV=production    # 或 development, testing

# 或在 Windows
set ANIMAL_AN_ENV=production
```

### 三種環境差異

| 特性 | 開發 | 測試 | 生產 |
|------|------|------|------|
| 自動重載 | ✓ | ✗ | ✗ |
| 調試日誌 | ✓ | 基本 | 僅 INFO |
| 資料庫備份 | ✗ | ✗ | ✓ |
| 驗證嚴格度 | 寬鬆 | 嚴格 | 嚴格 |
| 監聽埠 | 8000 | 8001 | 8000 |
| 監聽位址 | 127.0.0.1 | 127.0.0.1 | 0.0.0.0 |

### 查看當前配置

```bash
python config/environments.py
```

---

## 資料庫備份和恢復

### 建立備份

```bash
# 自動備份（時間戳命名）
python -m utils.backup create

# 輸出示例
# ✓ Backup created: animal_an_backup_20260701_120000.db
```

### 列出備份

```bash
python -m utils.backup list

# 輸出示例
# Database backups for: data/animal_an.db
# ======================================================================
# Backup File                                    Size Created             
# ----------------------------------------------------------------------
# animal_an_backup_20260701_120000.db        292.0 KB 2026-06-12 23:47:18 
# animal_an_backup_20260630_150000.db        290.5 KB 2026-06-30 15:00:00 
# ======================================================================
```

### 恢復備份

```bash
# 從備份恢復（自動建立安全備份）
python -m utils.backup restore animal_an_backup_20260630_150000.db

# 或指定完整路徑
python -m utils.backup restore data/animal_an_backup_20260630_150000.db
```

### 自動清理舊備份

```bash
# 刪除 30 天前的備份
python -m utils.backup clean --days 30

# 刪除 90 天前的備份
python -m utils.backup clean --days 90
```

### 定期備份（Linux/macOS）

編輯 crontab：

```bash
crontab -e

# 每天午夜建立備份
0 0 * * * /path/to/venv/bin/python -m utils.backup create

# 每月 1 日清理 90 天前的備份
0 2 1 * * /path/to/venv/bin/python -m utils.backup clean --days 90
```

---

## 資料匯入

### CSV 匯入檔案格式

在 `sample_data/` 目錄中建立 CSV 檔案。支持的檔案：

#### 1. `suppliers.csv` - 供應商主檔

```csv
code,name,short_name,supplier_type,country,contact_person,phone,email,address,credit_term_days,is_active
SUP-001,日本維生素進口,日本維,MANUFACTURER,Japan,田中太郎,+81-90-1234-5678,tanaka@example.jp,東京都渋谷區,30,true
```

#### 2. `customers.csv` - 客戶主檔

```csv
code,name,short_name,customer_type,contact_person,phone,email,address,credit_term_days,is_active
CUST-001,永春牧場,永春,VET_CLINIC,李經理,886-2-2345-6789,li@example.tw,台北市中山區,30,true
```

#### 3. `materials.csv` - 原裝品

```csv
code,name,description,unit,quantity,min_quantity,product_type,storage_type,is_active
MAT-001,維A粉,美國進口維A粉,kg,100,20,SUPPLEMENT,ROOM_TEMP,true
```

#### 4. `products.csv` - 分裝品

```csv
code,name,product_type,storage_type,package_type,unit,selling_price,spec,manufacturer,is_active
PROD-001,維A 100ml,SUPPLEMENT,ROOM_TEMP,BOTTLE,瓶,2500,100ml,東京製藥,true
```

### 執行匯入

```bash
# 建立樣本數據目錄
mkdir sample_data

# 將 CSV 檔案放入 sample_data/

# 執行匯入
python scripts/import_data.py ./sample_data/

# 輸出示例
# ======================================================================
# IMPORT SUMMARY
# ======================================================================
# Suppliers:        2
# Customers:        1
# Materials:        5
# Products:         10
# Errors:           0
# ======================================================================
```

### 匯入驗證規則

- **必填欄位**：code, name
- **唯一性**：code 必須唯一（重複會跳過）
- **資料型態**：自動轉換（失敗時記錄警告）
- **可選欄位**：大多數欄位可為空

---

## 故障排查

### 資料庫連接錯誤

**症狀**：`sqlite3.DatabaseError: database disk image is malformed`

**解決方案**：
```bash
# 1. 還原最近的備份
python -m utils.backup restore <latest_backup>

# 2. 或重建資料庫（警告：會失去資料）
rm data/animal_an.db
python -c "from models.database import db_manager; db_manager.init_db()"
```

### 遷移失敗

**症狀**：`RuntimeError: Database migration failed`

**解決方案**：
```bash
# 1. 檢查備份
python -m utils.backup list

# 2. 還原到遷移前版本
python -m utils.backup restore animal_an_pre_v03_*.db

# 3. 重新運行遷移
python scripts/migrate_v03.py
```

### 埠已被佔用

**症狀**：`Address already in use: ('127.0.0.1', 8000)`

**解決方案**：
```bash
# 方案 1：使用不同埠
python -m uvicorn web.app:app --port 8001

# 方案 2：查找並結束佔用進程（Linux/macOS）
lsof -i :8000
kill -9 <PID>

# 方案 2：查找並結束佔用進程（Windows）
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### 磁碟空間不足

**症狀**：`OSError: [Errno 28] No space left on device`

**解決方案**：
```bash
# 1. 清理舊備份
python -m utils.backup clean --days 7

# 2. 檢查磁碟空間
df -h                          # macOS/Linux
dir C:\                        # Windows

# 3. 清理日誌
rm -rf logs/*.log              # 保留 30 天日誌
```

### 性能緩慢

**症狀**：API 響應時間過長

**優化方案**：
```bash
# 1. 優化資料庫
python -c "
from models.database import db_manager
from sqlalchemy import text
db_manager.init_db()
session = db_manager.get_session()
session.execute(text('VACUUM;'))
session.commit()
"

# 2. 使用多工作進程（生產）
python -m uvicorn web.app:app --workers 4 --host 0.0.0.0

# 3. 監控資源使用
htop                           # Linux
top                            # macOS
tasklist                       # Windows
```

---

## 日誌檔案

### 日誌位置

```
logs/
├── 202606.log          # 月度日誌（縊月份）
├── 202607.log
└── ...
```

### 檢視日誌

```bash
# 查看最新日誌
tail -f logs/202607.log

# 搜尋錯誤
grep ERROR logs/202607.log

# 查看特定時間範圍
grep "2026-07-01 12:" logs/202607.log
```

---

## 維護清單

### 日常維護

- ✓ 監控應用日誌
- ✓ 檢查磁碟空間
- ✓ 驗證資料庫連接

### 週間維護

- ✓ 建立備份（如未自動）
- ✓ 清理舊日誌（>30 天）
- ✓ 檢視效能指標

### 月度維護

- ✓ 完整資料庫備份
- ✓ 清理超過 90 天的備份
- ✓ 驗證還原流程

---

## 支援和回饋

如有問題，請參考：
- 文檔：[README.md](README.md)
- 會計設計：[accounting_database_design.md](docs/accounting_database_design.md)
- GitHub：https://github.com/AgendaLu/animal-an-erp
