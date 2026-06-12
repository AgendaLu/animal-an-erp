# 🧮 會計核對帳務資料庫結構設計

**版本：** 1.0  
**最後更新：** 2026-06-12  
**適用場景：** 動物飼料/養殖場 ERP 會計核帳模組

---

## 📑 目錄
1. [核心概念](#核心概念)
2. [資料表設計](#資料表設計)
3. [報表結構](#報表結構)
4. [資料流程](#資料流程)
5. [Excel/CSV 匯入範本](#excelcsv-匯入範本)
6. [會計核帳流程](#會計核帳流程)

---

## 核心概念

### 帳務雙分錄原則
所有交易必須記錄**雙邊**：
- **買進側**：採購發票 + 付款記錄
- **銷售側**：銷售發票 + 收款記錄（或應收帳款）

### 庫存三層構造
```
原裝品進貨 (BulkBatch)
    ↓ [庫存交易 InventoryTransaction]
    ↓
分裝/銷售 (Product Batch)
    ↓ [銷售交易 SalesTransaction]
    ↓
客戶出貨確認
```

### 稅務考量
- **進項稅** (VAT In)：採購發票上的稅額
- **銷項稅** (VAT Out)：銷售發票上的稅額
- **月度申報**：銷項稅 - 進項稅 = 應納稅額

---

## 資料表設計

### 1. 銷售交易明細表 `sales_transactions`
記錄每一筆銷售交易的完整資訊（一行 = 一個商品品項）

| 欄位名稱 | 型態 | 必填 | 說明 |
|---------|------|------|------|
| `id` | INTEGER | ✅ | 交易 ID (primary key) |
| `sales_invoice_id` | INTEGER | ✅ | 所屬銷售發票 (FK → sales_invoices) |
| `product_code` | VARCHAR(50) | ✅ | 商品代碼 |
| `product_name` | VARCHAR(100) | ✅ | 商品名稱 |
| `product_batch_number` | VARCHAR(50) | ⚠️ | 分裝品批號（可追溯來源） |
| `quantity` | FLOAT | ✅ | 銷售數量 |
| `unit` | VARCHAR(20) | ✅ | 銷售單位（瓶/包/組） |
| `unit_price` | FLOAT | ✅ | 銷售單價 |
| `line_amount` | FLOAT | ✅ | 行小計 = quantity × unit_price（不含稅） |
| `tax_rate` | FLOAT | ✅ | 稅率（%，通常 5% 或 0%） |
| `tax_amount` | FLOAT | ✅ | 稅額 = line_amount × tax_rate / 100 |
| `line_total` | FLOAT | ✅ | 行合計 = line_amount + tax_amount |
| `cost_per_unit` | FLOAT | ⚠️ | 該批商品的進價成本（用於損益計算） |
| `gross_profit` | FLOAT | ⚠️ | 毛利 = (unit_price - cost_per_unit) × quantity |
| `reference_type` | VARCHAR(20) | ⚠️ | 來源參考類型（SO = 銷售單, DIRECT = 直接開票） |
| `reference_id` | INTEGER | ⚠️ | 來源參考 ID（採購單/銷售單 ID） |
| `notes` | TEXT | ⚠️ | 備註（特殊折扣、取消原因等） |
| `created_at` | DATETIME | ✅ | 建立時間 |

**索引建議：**
```sql
CREATE INDEX idx_sales_tx_invoice ON sales_transactions(sales_invoice_id);
CREATE INDEX idx_sales_tx_product ON sales_transactions(product_code);
CREATE INDEX idx_sales_tx_batch ON sales_transactions(product_batch_number);
CREATE INDEX idx_sales_tx_date ON sales_transactions(created_at);
```

---

### 2. 銷售發票表 `sales_invoices`
記錄每一張銷售發票的統計資訊

| 欄位名稱 | 型態 | 必填 | 說明 |
|---------|------|------|------|
| `id` | INTEGER | ✅ | 發票 ID |
| `invoice_number` | VARCHAR(30) | ✅ | 發票號碼（格式：2024-0001）唯一 |
| `customer_code` | VARCHAR(20) | ✅ | 客戶代碼 (FK → customers) |
| `customer_name` | VARCHAR(100) | ✅ | 客戶名稱 |
| `invoice_date` | DATE | ✅ | 開票日期 |
| `due_date` | DATE | ✅ | 應收日期（帳期後）|
| `total_amount_pretax` | FLOAT | ✅ | 合計（稅前）= SUM(line_amount) |
| `total_tax_amount` | FLOAT | ✅ | 合計稅額 = SUM(tax_amount) |
| `total_amount_with_tax` | FLOAT | ✅ | 合計（稅後）= total_amount_pretax + total_tax_amount |
| `payment_status` | ENUM | ✅ | 付款狀態（UNPAID/PARTIAL/PAID） |
| `payment_method` | VARCHAR(50) | ⚠️ | 收款方式（現金/轉帳/支票） |
| `paid_amount` | FLOAT | ⚠️ | 已收金額 |
| `remaining_balance` | FLOAT | ⚠️ | 未收金額 = total_amount_with_tax - paid_amount |
| `currency` | VARCHAR(10) | ✅ | 幣別（TWD/JPY/USD） |
| `notes` | TEXT | ⚠️ | 備註 |
| `sales_order_id` | INTEGER | ⚠️ | 原始銷售單 ID (FK → sales_orders) |
| `tax_classification` | VARCHAR(20) | ✅ | 稅務分類（DOMESTIC/EXPORT/EXEMPT） |
| `unified_invoice_number` | VARCHAR(20) | ⚠️ | 統一發票號碼（台灣） |
| `created_at` | DATETIME | ✅ | 建立時間 |
| `created_by` | VARCHAR(50) | ✅ | 建立人 |
| `issued_at` | DATETIME | ⚠️ | 開票時間（可能晚於建立） |

**索引建議：**
```sql
CREATE UNIQUE INDEX idx_sales_inv_number ON sales_invoices(invoice_number);
CREATE INDEX idx_sales_inv_customer ON sales_invoices(customer_code);
CREATE INDEX idx_sales_inv_date ON sales_invoices(invoice_date);
CREATE INDEX idx_sales_inv_status ON sales_invoices(payment_status);
```

---

### 3. 採購交易明細表 `purchase_transactions`
記錄每一筆採購交易的完整資訊

| 欄位名稱 | 型態 | 必填 | 說明 |
|---------|------|------|------|
| `id` | INTEGER | ✅ | 交易 ID |
| `purchase_invoice_id` | INTEGER | ✅ | 所屬採購發票 (FK → purchase_invoices) |
| `bulk_item_code` | VARCHAR(50) | ✅ | 原裝品代碼 |
| `bulk_item_name` | VARCHAR(100) | ✅ | 原裝品名稱 |
| `bulk_batch_number` | VARCHAR(50) | ✅ | 原裝品批號 |
| `quantity` | FLOAT | ✅ | 採購數量 |
| `unit` | VARCHAR(20) | ✅ | 採購單位（棧板/桶/箱） |
| `unit_price` | FLOAT | ✅ | 採購單價 |
| `line_amount` | FLOAT | ✅ | 行小計（稅前）= quantity × unit_price |
| `tax_rate` | FLOAT | ✅ | 稅率（%） |
| `tax_amount` | FLOAT | ✅ | 稅額 = line_amount × tax_rate / 100 |
| `line_total` | FLOAT | ✅ | 行合計（稅後）= line_amount + tax_amount |
| `manufacturing_date` | DATE | ⚠️ | 製造日期 |
| `expiry_date` | DATE | ⚠️ | 有效期截止日期 |
| `lot_number` | VARCHAR(50) | ⚠️ | 原廠批號 |
| `reference_type` | VARCHAR(20) | ⚠️ | 來源參考（PO = 採購單） |
| `reference_id` | INTEGER | ⚠️ | 採購單 ID (FK → purchase_orders) |
| `received_date` | DATE | ⚠️ | 實際收貨日期 |
| `received_qty` | FLOAT | ⚠️ | 實收數量（與訂購數量可能不同） |
| `qc_status` | VARCHAR(20) | ⚠️ | 品質檢查狀態（PASS/FAIL/PENDING） |
| `notes` | TEXT | ⚠️ | 備註 |
| `created_at` | DATETIME | ✅ | 建立時間 |

**索引建議：**
```sql
CREATE INDEX idx_purchase_tx_invoice ON purchase_transactions(purchase_invoice_id);
CREATE INDEX idx_purchase_tx_bulk ON purchase_transactions(bulk_item_code);
CREATE INDEX idx_purchase_tx_batch ON purchase_transactions(bulk_batch_number);
CREATE INDEX idx_purchase_tx_date ON purchase_transactions(created_at);
```

---

### 4. 採購發票表 `purchase_invoices`
記錄從供應商收到的發票

| 欄位名稱 | 型態 | 必填 | 說明 |
|---------|------|------|------|
| `id` | INTEGER | ✅ | 發票 ID |
| `invoice_number` | VARCHAR(50) | ✅ | 供應商發票號碼（唯一+供應商） |
| `supplier_code` | VARCHAR(20) | ✅ | 供應商代碼 (FK → suppliers) |
| `supplier_name` | VARCHAR(100) | ✅ | 供應商名稱 |
| `invoice_date` | DATE | ✅ | 發票日期 |
| `due_date` | DATE | ✅ | 應付日期 |
| `total_amount_pretax` | FLOAT | ✅ | 合計（稅前） |
| `total_tax_amount` | FLOAT | ✅ | 合計進項稅額 |
| `total_amount_with_tax` | FLOAT | ✅ | 合計（稅後） |
| `payment_status` | ENUM | ✅ | 付款狀態（UNPAID/PARTIAL/PAID） |
| `paid_amount` | FLOAT | ⚠️ | 已付金額 |
| `remaining_balance` | FLOAT | ⚠️ | 待付金額 |
| `payment_method` | VARCHAR(50) | ⚠️ | 付款方式 |
| `currency` | VARCHAR(10) | ✅ | 幣別 |
| `purchase_order_id` | INTEGER | ⚠️ | 原始採購單 ID (FK → purchase_orders) |
| `tax_classification` | VARCHAR(20) | ✅ | 稅務分類（DOMESTIC/IMPORT/EXEMPT） |
| `vat_registration` | VARCHAR(20) | ⚠️ | 供應商統一編號 |
| `notes` | TEXT | ⚠️ | 備註 |
| `created_at` | DATETIME | ✅ | 建立時間 |
| `created_by` | VARCHAR(50) | ✅ | 建立人 |

**索引建議：**
```sql
CREATE UNIQUE INDEX idx_purchase_inv_supplier 
  ON purchase_invoices(supplier_code, invoice_number);
CREATE INDEX idx_purchase_inv_date ON purchase_invoices(invoice_date);
CREATE INDEX idx_purchase_inv_status ON purchase_invoices(payment_status);
```

---

### 5. 付款記錄表 `payment_records`
記錄所有進出款項（採購付款 + 銷售收款）

| 欄位名稱 | 型態 | 必填 | 說明 |
|---------|------|------|------|
| `id` | INTEGER | ✅ | 付款記錄 ID |
| `payment_number` | VARCHAR(30) | ✅ | 付款編號（唯一） |
| `payment_type` | ENUM | ✅ | 類型（PAYMENT_TO_SUPPLIER/RECEIPT_FROM_CUSTOMER） |
| `transaction_date` | DATE | ✅ | 交易日期 |
| `reference_type` | VARCHAR(20) | ✅ | 參考類型（INVOICE = 發票, PO = 採購單） |
| `reference_id` | INTEGER | ✅ | 參考 ID（sales_invoices.id 或 purchase_invoices.id） |
| `supplier_or_customer_code` | VARCHAR(20) | ✅ | 對方代碼 |
| `supplier_or_customer_name` | VARCHAR(100) | ✅ | 對方名稱 |
| `amount` | FLOAT | ✅ | 付款/收款金額（含稅） |
| `currency` | VARCHAR(10) | ✅ | 幣別 |
| `payment_method` | VARCHAR(50) | ✅ | 付款方式（TRANSFER/CHECK/CASH） |
| `bank_account_from` | VARCHAR(50) | ⚠️ | 付款帳號（我方） |
| `bank_account_to` | VARCHAR(50) | ⚠️ | 收款帳號（對方） |
| `check_number` | VARCHAR(50) | ⚠️ | 支票號碼（若為支票） |
| `transaction_reference` | VARCHAR(100) | ⚠️ | 轉帳參考號/備註編號 |
| `notes` | TEXT | ⚠️ | 備註 |
| `created_at` | DATETIME | ✅ | 建立時間 |
| `created_by` | VARCHAR(50) | ✅ | 建立人 |
| `verified_at` | DATETIME | ⚠️ | 驗證時間（對帳用） |
| `verified_by` | VARCHAR(50) | ⚠️ | 驗證人 |

**索引建議：**
```sql
CREATE UNIQUE INDEX idx_payment_number ON payment_records(payment_number);
CREATE INDEX idx_payment_type ON payment_records(payment_type);
CREATE INDEX idx_payment_date ON payment_records(transaction_date);
CREATE INDEX idx_payment_reference ON payment_records(reference_type, reference_id);
```

---

### 6. 庫存移動明細表 `inventory_movements`
完整的庫存進出帳簿（進貨 + 銷售 + 損耗 + 盤點差異）

| 欄位名稱 | 型態 | 必填 | 說明 |
|---------|------|------|------|
| `id` | INTEGER | ✅ | 移動 ID |
| `movement_date` | DATE | ✅ | 移動日期 |
| `item_type` | ENUM | ✅ | 品項類型（BULK/PRODUCT） |
| `item_code` | VARCHAR(50) | ✅ | 商品代碼 |
| `item_name` | VARCHAR(100) | ✅ | 商品名稱 |
| `batch_number` | VARCHAR(50) | ✅ | 批號 |
| `movement_type` | ENUM | ✅ | 移動類型（IN/OUT/ADJUST） |
| `quantity_change` | FLOAT | ✅ | 數量變化（±值） |
| `unit_price` | FLOAT | ⚠️ | 單價（用於估價） |
| `amount` | FLOAT | ⚠️ | 金額 = quantity_change × unit_price |
| `balance_before` | FLOAT | ⚠️ | 移動前餘額 |
| `balance_after` | FLOAT | ✅ | 移動後餘額 |
| `reference_type` | VARCHAR(20) | ✅ | 來源（PO/SO/REPACK/INVENTORY_COUNT/ADJUSTMENT） |
| `reference_id` | INTEGER | ⚠️ | 相關交易 ID |
| `notes` | TEXT | ⚠️ | 備註 |
| `created_at` | DATETIME | ✅ | 建立時間 |
| `created_by` | VARCHAR(50) | ✅ | 建立人 |

**索引建議：**
```sql
CREATE INDEX idx_inv_mov_item ON inventory_movements(item_code, batch_number);
CREATE INDEX idx_inv_mov_date ON inventory_movements(movement_date);
CREATE INDEX idx_inv_mov_type ON inventory_movements(movement_type);
```

---

### 7. 庫存盤點表 `inventory_counts`
月度或定期盤點紀錄（物理盤點 vs 帳面餘額比對）

| 欄位名稱 | 型態 | 必填 | 說明 |
|---------|------|------|------|
| `id` | INTEGER | ✅ | 盤點 ID |
| `count_number` | VARCHAR(30) | ✅ | 盤點編號（唯一） |
| `count_date` | DATE | ✅ | 盤點日期 |
| `item_code` | VARCHAR(50) | ✅ | 商品代碼 |
| `item_name` | VARCHAR(100) | ✅ | 商品名稱 |
| `batch_number` | VARCHAR(50) | ⚠️ | 批號（可選，若按批盤點） |
| `account_balance` | FLOAT | ✅ | 帳面餘額 |
| `physical_count` | FLOAT | ✅ | 實際盤點數 |
| `variance` | FLOAT | ✅ | 盤差 = physical_count - account_balance |
| `variance_reason` | VARCHAR(200) | ⚠️ | 盤差原因（損耗/誤差/偷竊等） |
| `unit_price` | FLOAT | ⚠️ | 單價（用於損益計算） |
| `variance_amount` | FLOAT | ⚠️ | 盤差金額 = variance × unit_price |
| `notes` | TEXT | ⚠️ | 備註 |
| `created_at` | DATETIME | ✅ | 建立時間 |
| `created_by` | VARCHAR(50) | ✅ | 盤點人 |
| `verified_at` | DATETIME | ⚠️ | 驗證時間 |
| `verified_by` | VARCHAR(50) | ⚠️ | 驗證人 |

**索引建議：**
```sql
CREATE INDEX idx_count_number ON inventory_counts(count_number);
CREATE INDEX idx_count_date ON inventory_counts(count_date);
CREATE INDEX idx_count_item ON inventory_counts(item_code);
```

---

### 8. 稅務記錄表 `tax_records`
月度稅務彙總與申報追蹤

| 欄位名稱 | 型態 | 必填 | 說明 |
|---------|------|------|------|
| `id` | INTEGER | ✅ | 記錄 ID |
| `tax_period` | VARCHAR(10) | ✅ | 稅務期間（YYYY-MM） |
| `tax_type` | ENUM | ✅ | 稅別（VAT/BUSINESS_TAX/INCOME_TAX） |
| `total_sales_amount` | FLOAT | ✅ | 銷售合計（稅前） |
| `total_sales_tax` | FLOAT | ✅ | 銷項稅額（應納稅額） |
| `total_purchase_amount` | FLOAT | ✅ | 採購合計（稅前） |
| `total_purchase_tax` | FLOAT | ✅ | 進項稅額（可扣抵） |
| `net_tax_payable` | FLOAT | ✅ | 應納稅額 = total_sales_tax - total_purchase_tax |
| `sales_invoice_count` | INTEGER | ⚠️ | 銷售發票張數 |
| `purchase_invoice_count` | INTEGER | ⚠️ | 採購發票張數 |
| `filing_status` | ENUM | ✅ | 申報狀態（DRAFT/FILED/CONFIRMED） |
| `filing_date` | DATE | ⚠️ | 申報日期 |
| `filing_reference_number` | VARCHAR(50) | ⚠️ | 申報編號 |
| `payment_due_date` | DATE | ⚠️ | 應納日期 |
| `payment_status` | ENUM | ⚠️ | 繳稅狀態（UNPAID/PAID） |
| `payment_date` | DATE | ⚠️ | 繳稅日期 |
| `notes` | TEXT | ⚠️ | 備註 |
| `created_at` | DATETIME | ✅ | 建立時間 |
| `created_by` | VARCHAR(50) | ✅ | 建立人 |

**索引建議：**
```sql
CREATE UNIQUE INDEX idx_tax_period ON tax_records(tax_period, tax_type);
CREATE INDEX idx_tax_filing_status ON tax_records(filing_status);
```

---

### 9. 應收應付帳款表 `accounts_receivable` / `accounts_payable`

#### 應收帳款 `accounts_receivable`
| 欄位名稱 | 型態 | 必填 | 說明 |
|---------|------|------|------|
| `id` | INTEGER | ✅ | 帳款 ID |
| `customer_code` | VARCHAR(20) | ✅ | 客戶代碼 |
| `customer_name` | VARCHAR(100) | ✅ | 客戶名稱 |
| `sales_invoice_id` | INTEGER | ✅ | 銷售發票 ID |
| `invoice_number` | VARCHAR(30) | ✅ | 發票號碼 |
| `original_amount` | FLOAT | ✅ | 原始帳款（含稅） |
| `paid_amount` | FLOAT | ✅ | 已收金額 |
| `outstanding_amount` | FLOAT | ✅ | 未收金額 = original_amount - paid_amount |
| `invoice_date` | DATE | ✅ | 開票日期 |
| `due_date` | DATE | ✅ | 應收日期 |
| `days_overdue` | INTEGER | ⚠️ | 逾期天數（計算欄位） |
| `overdue_status` | VARCHAR(20) | ⚠️ | 逾期狀態（ON_TIME/OVERDUE） |
| `notes` | TEXT | ⚠️ | 備註 |
| `last_payment_date` | DATE | ⚠️ | 最後收款日期 |

#### 應付帳款 `accounts_payable`
| 欄位名稱 | 型態 | 必填 | 說明 |
|---------|------|------|------|
| `id` | INTEGER | ✅ | 帳款 ID |
| `supplier_code` | VARCHAR(20) | ✅ | 供應商代碼 |
| `supplier_name` | VARCHAR(100) | ✅ | 供應商名稱 |
| `purchase_invoice_id` | INTEGER | ✅ | 採購發票 ID |
| `invoice_number` | VARCHAR(50) | ✅ | 發票號碼 |
| `original_amount` | FLOAT | ✅ | 原始帳款（含稅） |
| `paid_amount` | FLOAT | ✅ | 已付金額 |
| `outstanding_amount` | FLOAT | ✅ | 待付金額 = original_amount - paid_amount |
| `invoice_date` | DATE | ✅ | 發票日期 |
| `due_date` | DATE | ✅ | 應付日期 |
| `days_overdue` | INTEGER | ⚠️ | 逾期天數 |
| `overdue_status` | VARCHAR(20) | ⚠️ | 逾期狀態 |
| `notes` | TEXT | ⚠️ | 備註 |
| `last_payment_date` | DATE | ⚠️ | 最後付款日期 |

---

## 報表結構

### 📊 日銷售報表 `daily_sales_report`

```
日期：2024-06-12
=================================================
客戶代碼 | 客戶名稱 | 發票號 | 品項數 | 銷售額（稅前）| 稅額 | 銷售額（稅後）
CUST-001| 永春牧場 | INV-001| 3     | 5,000        | 250  | 5,250
CUST-002| 美豬集團 | INV-002| 2     | 8,000        | 400  | 8,400
=================================================
合計           | 5     | 13,000       | 650  | 13,650
```

**所需欄位：**
- invoice_date, customer_code, customer_name, invoice_number
- product_code, product_name, quantity, unit, unit_price
- line_amount (稅前), tax_amount, line_total (稅後)
- gross_profit （毛利 = (unit_price - cost) × quantity）

**SQL 查詢：**
```sql
SELECT 
  si.invoice_date,
  si.customer_code,
  c.name AS customer_name,
  si.invoice_number,
  COUNT(st.id) AS item_count,
  SUM(st.line_amount) AS total_pretax,
  SUM(st.tax_amount) AS total_tax,
  SUM(st.line_total) AS total_withtax,
  SUM(st.gross_profit) AS gross_profit
FROM sales_invoices si
JOIN customers c ON si.customer_code = c.code
JOIN sales_transactions st ON si.id = st.sales_invoice_id
WHERE si.invoice_date = ?
GROUP BY si.id
ORDER BY si.invoice_date DESC;
```

---

### 📊 月進銷存報表 `monthly_inventory_report`

```
期間：2024-06-01 ~ 2024-06-30

商品代碼 | 商品名稱 | 期初 | 進貨 | 銷售 | 損耗 | 期末 | 進貨成本 | 銷售收入 | 庫存成本 | 毛利
PROD-001 | 維A 100ml | 100 | 50  | 80  | 2  | 68  | 15,000  | 20,000  | 20,400  | 4,600
=================================================
合計     |          | 200 | 150 | 150 | 5  | 195 | 45,000  | 60,000  | 58,500  | 12,000
```

**SQL 查詢（以 product 為主）：**
```sql
SELECT 
  p.code,
  p.name,
  -- 期初
  (SELECT COALESCE(SUM(im.balance_before), 0)
   FROM inventory_movements im
   WHERE im.item_code = p.code
   AND im.movement_date >= date('2024-06-01')
   LIMIT 1) AS opening_balance,
  -- 進貨
  COALESCE(SUM(CASE WHEN im.movement_type = 'IN' THEN im.quantity_change ELSE 0 END), 0) AS purchases,
  -- 銷售
  COALESCE(SUM(CASE WHEN im.movement_type = 'OUT' THEN ABS(im.quantity_change) ELSE 0 END), 0) AS sales,
  -- 期末
  COALESCE(SUM(im.balance_after), 0) AS closing_balance,
  -- 成本
  COALESCE(SUM(CASE WHEN im.movement_type = 'IN' THEN im.amount ELSE 0 END), 0) AS purchase_cost,
  COALESCE(SUM(CASE WHEN im.movement_type = 'OUT' THEN im.amount ELSE 0 END), 0) AS cogs
FROM products p
LEFT JOIN inventory_movements im ON p.code = im.item_code
  AND im.movement_date BETWEEN '2024-06-01' AND '2024-06-30'
GROUP BY p.code, p.name
ORDER BY p.code;
```

---

### 📊 庫存損益報表 `inventory_loss_report`

```
期間：2024-06-01 ~ 2024-06-30

商品代碼 | 原因       | 盤差數量 | 單價 | 盤差金額
PROD-001 | 自然損耗   | -2     | 260 | -520
PROD-002 | 配方錯誤   | -1     | 240 | -240
PROD-003 | 誤算發現   | +3     | 180 | +540
=================================================
合計     |           | 0      |     | -220
```

**所需表格：** inventory_counts

---

### 📊 應收帳款報表 `accounts_receivable_aging`

```
期間：2024-06-12 當前

客戶代碼 | 客戶名稱 | 發票號 | 發票日 | 應收日 | 原始金額 | 已收 | 未收 | 逾期天數
CUST-001| 永春牧場 | INV-001| 2024-05-01 | 2024-06-01 | 5,250 | 0 | 5,250 | 11
CUST-002| 美豬集團 | INV-002| 2024-05-15 | 2024-06-15 | 8,400 | 0 | 8,400 | 0（未逾期）
=================================================
應收帳款合計 |          | 13,650 | 0 | 13,650 | 
  ├─ 未逾期 | 8,400 |  |
  └─ 逾期   | 5,250 |  |
```

**所需表格：** accounts_receivable

---

### 📊 應付帳款報表 `accounts_payable_aging`

```
期間：2024-06-12 當前

供應商代碼 | 供應商名稱 | 發票號 | 發票日 | 應付日 | 原始金額 | 已付 | 待付 | 逾期狀態
SUP-001   | 天然維    | PUI-001| 2024-05-01 | 2024-05-31 | 25,000 | 0 | 25,000 | ⚠️ 逾期 11 天
SUP-002   | 益生菌    | PUI-002| 2024-06-01 | 2024-07-01 | 30,000 | 0 | 30,000 | ✓ 未逾期
=================================================
應付帳款合計 |          | 55,000 | 0 | 55,000 |
  ├─ 未逾期 | 30,000 |  |
  └─ 逾期   | 25,000 |  |
```

**所需表格：** accounts_payable

---

### 📊 月度銷售稅務申報表 `monthly_tax_summary`

```
申報期間：2024年06月

銷售稅務摘要
=================================================
銷售發票總數      | 15 張
銷售總額（稅前）  | ¥1,500,000
銷項稅額 5%      | ¥75,000
銷售總額（稅後）  | ¥1,575,000

採購稅務摘要
=================================================
採購發票總數      | 8 張
採購總額（稅前）  | ¥900,000
進項稅額 5%      | ¥45,000
採購總額（稅後）  | ¥945,000

應納稅額
=================================================
銷項稅額          | ¥75,000
進項稅額          | -¥45,000
應納稅額          | ¥30,000（需於次月繳納）
```

**所需表格：** tax_records

---

### 📊 發票開立與請款報告

```
銷售發票明細
發票號碼 | 開票日 | 客戶名稱 | 品項  | 金額（稅前）| 稅額 | 金額（稅後）| 應收日 | 收款狀態
INV-0001| 2024-06-01 | 永春牧場 | 維A粉×2 | 5,000 | 250 | 5,250 | 2024-07-01 | 未收
INV-0002| 2024-06-05 | 美豬集團 | 益生菌×1 | 8,000 | 400 | 8,400 | 2024-07-20 | 未收
```

---

## 資料流程

### 銷售流程圖

```
1. 客戶下單 → SalesOrder (現有)
    ↓ (確認出貨)
2. 開立銷售發票 → sales_invoices + sales_transactions
    ↓ (記錄庫存移動)
3. 更新庫存 → inventory_movements
    ↓ (客戶收款)
4. 記錄付款 → payment_records
    ↓ (更新應收帳款)
5. 更新應收帳款 → accounts_receivable
    ↓ (月底稅務彙總)
6. 產生稅務記錄 → tax_records
```

### 採購流程圖

```
1. 向供應商下單 → PurchaseOrder (現有)
    ↓ (收到商品)
2. 記錄收貨 → purchase_transactions + bulk_batches
    ↓ (供應商發票到達)
3. 記錄採購發票 → purchase_invoices + purchase_transactions
    ↓ (更新庫存)
4. 更新庫存 → inventory_movements
    ↓ (付款給供應商)
5. 記錄付款 → payment_records
    ↓ (更新應付帳款)
6. 更新應付帳款 → accounts_payable
    ↓ (月底稅務彙總)
7. 產生稅務記錄 → tax_records
```

---

## Excel/CSV 匯入範本

### 1. 銷售發票匯入範本 `sales_invoices_import.csv`

```csv
invoice_number,customer_code,customer_name,invoice_date,due_date,payment_method,currency,notes
INV-2024-0001,CUST-001,永春牧場,2024-06-01,2024-07-01,TRANSFER,TWD,備註
INV-2024-0002,CUST-002,美豬集團,2024-06-05,2024-07-20,CHECK,TWD,預留
```

### 2. 銷售交易行項目範本 `sales_transactions_import.csv`

```csv
invoice_number,product_code,product_name,batch_number,quantity,unit,unit_price,tax_rate,cost_per_unit,notes
INV-2024-0001,PROD-001,維A粉 100ml,BATCH-2024-001,2,瓶,2500,5,2000,
INV-2024-0001,PROD-002,益生菌粉,BATCH-2024-002,1,包,1800,5,1500,
INV-2024-0002,PROD-001,維A粉 100ml,BATCH-2024-001,3,瓶,2500,5,2000,
```

### 3. 採購發票匯入範本 `purchase_invoices_import.csv`

```csv
invoice_number,supplier_code,supplier_name,invoice_date,due_date,payment_method,currency,vat_registration,notes
PUI-2024-0001,SUP-001,天然維進口,2024-05-01,2024-06-01,TRANSFER,JPY,123-4567890,
PUI-2024-0002,SUP-002,益生菌廠,2024-05-15,2024-06-15,CHECK,TWD,234-5678901,
```

### 4. 採購交易行項目範本 `purchase_transactions_import.csv`

```csv
invoice_number,bulk_item_code,bulk_item_name,batch_number,quantity,unit,unit_price,tax_rate,manufacturing_date,expiry_date,lot_number,received_date,received_qty,qc_status
PUI-2024-0001,BULK-001,維A粉,BATCH-2024-001,50,kg,300,5,2024-05-01,2026-05-01,ORIG-LOT-2024-001,2024-05-05,50,PASS
PUI-2024-0002,BULK-002,益生菌,BATCH-2024-002,20,kg,400,5,2024-05-10,2025-05-10,ORIG-LOT-2024-002,2024-05-20,20,PASS
```

### 5. 付款記錄匯入範本 `payment_records_import.csv`

```csv
payment_number,payment_type,transaction_date,reference_type,reference_id,supplier_or_customer_code,amount,currency,payment_method,bank_account_from,bank_account_to,notes
PAY-2024-0001,PAYMENT_TO_SUPPLIER,2024-06-01,INVOICE,PUI-2024-0001,SUP-001,25000,JPY,TRANSFER,CUST-BANK-001,SUP-BANK-001,定期付款
RCP-2024-0001,RECEIPT_FROM_CUSTOMER,2024-06-10,INVOICE,INV-2024-0001,CUST-001,5250,TWD,CHECK,CUST-BANK-001,COMPANY-BANK-001,支票號 CHK-001
```

### 6. 庫存盤點匯入範本 `inventory_counts_import.csv`

```csv
count_number,count_date,item_code,item_name,batch_number,account_balance,physical_count,variance_reason,unit_price
COUNT-2024-06,2024-06-30,PROD-001,維A粉 100ml,BATCH-2024-001,50,48,-2,自然損耗,260
COUNT-2024-06,2024-06-30,PROD-002,益生菌粉,BATCH-2024-002,30,31,+1,誤算發現,240
```

---

## 會計核帳流程

### 日終流程（每日）

```
1. 核對銷售發票
   - 銷售發票號碼連續性
   - 小計 = Σ(line_amount + tax_amount)
   
2. 核對應收帳款
   - 應收帳款合計 = 銷售發票 - 已收款
   - 逾期帳款提醒
   
3. 核對庫存
   - inventory_movements 記錄完整
   - balance_after 正確性
```

### 月終流程（每月底）

```
1. 月度銷售盤點
   - 銷售發票完整性檢查
   - 逐筆對帳交易明細
   
2. 月度採購盤點
   - 採購發票完整性檢查
   - 收貨確認
   
3. 庫存物理盤點
   - 依商品批號盤點
   - 記錄 inventory_counts
   - 計算盤差與原因
   
4. 應收應付帳款對帳
   - accounts_receivable vs 銷售發票
   - accounts_payable vs 採購發票
   - 確認逾期帳款
   
5. 稅務彙總
   - 計算月度銷項稅、進項稅
   - 生成 tax_records
   - 準備營業稅申報
   
6. 月結報表產出
   - 日銷售報表聚合
   - 月進銷存報表
   - 庫存損益報表
   - 應收應付帳款老化分析
```

### 查帳檢查點

```
✓ 銷售發票 ↔ 銷售交易 ↔ 應收帳款 ↔ 付款記錄
✓ 採購發票 ↔ 採購交易 ↔ 應付帳款 ↔ 付款記錄
✓ 庫存移動 ↔ 銷售交易（OUT）↔ 採購交易（IN）
✓ 月度盤點 vs 帳面餘額 → 損益計算
✓ 銷項稅 - 進項稅 = 應納稅額
✓ 逾期帳款追蹤（應收/應付）
```

---

## 資料驗證規則

### 必填欄位驗證
```python
REQUIRED_FIELDS = {
    'sales_invoices': [
        'invoice_number', 'customer_code', 'invoice_date', 
        'due_date', 'total_amount_with_tax'
    ],
    'sales_transactions': [
        'sales_invoice_id', 'product_code', 'quantity',
        'unit_price', 'tax_rate'
    ],
    'purchase_invoices': [
        'invoice_number', 'supplier_code', 'invoice_date',
        'due_date', 'total_amount_with_tax'
    ],
    'purchase_transactions': [
        'purchase_invoice_id', 'bulk_item_code', 'quantity',
        'unit_price', 'tax_rate'
    ],
}
```

### 邏輯驗證
```python
VALIDATION_RULES = {
    'sales_transactions': {
        'line_amount': 'quantity * unit_price',
        'tax_amount': 'line_amount * (tax_rate / 100)',
        'line_total': 'line_amount + tax_amount',
        'gross_profit': '(unit_price - cost_per_unit) * quantity'
    },
    'sales_invoices': {
        'total_amount_pretax': 'SUM(sales_transactions.line_amount)',
        'total_tax_amount': 'SUM(sales_transactions.tax_amount)',
        'total_amount_with_tax': 'total_amount_pretax + total_tax_amount',
        'remaining_balance': 'total_amount_with_tax - paid_amount'
    },
    'inventory_movements': {
        'balance_after': 'balance_before + quantity_change',
        'amount': 'quantity_change * unit_price'
    },
    'tax_records': {
        'net_tax_payable': 'total_sales_tax - total_purchase_tax'
    }
}
```

---

## 次級設計考量

### 幣別換算
若涉及多幣別交易（JPY, USD, TWD），需要：
- `exchange_rates` 表記錄日匯率
- 每筆交易記錄當日匯率
- 稅務申報時統一轉換為當地幣別

### 分期付款
若客戶分期支付，`payment_records` 可能多筆對應一張 `sales_invoices`：
```sql
SELECT si.invoice_number, COUNT(pr.id) AS payment_count
FROM sales_invoices si
LEFT JOIN payment_records pr ON si.id = pr.reference_id
WHERE pr.payment_type = 'RECEIPT_FROM_CUSTOMER'
GROUP BY si.id;
```

### 退貨處理
增加 `sales_returns` 表，記錄客戶退貨（負向銷售交易）

### 銀行對帳
整合 `payment_records` 與銀行對帳單，自動標示核對狀態

---

## 下一步行動清單

- [ ] 建立上述 9 張表的 SQLAlchemy ORM 模型
- [ ] 編寫導入腳本（CSV/Excel → 資料庫）
- [ ] 建立各報表的 SQL 查詢樣板
- [ ] 設計報表 UI（FastAPI 端點 + 前端表格）
- [ ] 實現月結自動化流程
- [ ] 整合稅務申報邏輯
- [ ] 建立查帳檢查清單與工作流

