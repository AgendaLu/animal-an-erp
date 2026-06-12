"""會計模組 ViewModel — 發票/收付款/報表的業務邏輯層。

職責：
- 建立銷售/採購發票（自動計算行金額、發票合計，並同步 AR/AP）
- 記錄收付款（核銷發票、更新 AR/AP 餘額與狀態）
- 報表查詢：日銷售、月稅務彙總（銷項稅 − 進項稅）、AR/AP 帳齡
"""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.accounting import (
    SalesInvoice, SalesTransaction,
    PurchaseInvoice, PurchaseTransaction,
    PaymentRecord, PaymentType, InvoicePaymentStatus,
    TaxRecord, TaxType, FilingStatus,
    AccountsReceivable, AccountsPayable,
)


class AccountingViewModel:
    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------ invoices

    def create_sales_invoice(self, header: dict, lines: list[dict]) -> SalesInvoice:
        """建立銷售發票 + 明細，並開立對應應收帳款。

        header: invoice_number, customer_code, customer_name,
                invoice_date, due_date, (optional) currency/notes/...
        lines:  product_code, product_name, quantity, unit, unit_price,
                (optional) tax_rate, cost_per_unit, product_batch_number, ...
        """
        if not lines:
            raise ValueError("發票至少需要一筆明細")
        inv = SalesInvoice(**header)
        for ld in lines:
            line = SalesTransaction(line_amount=0, **ld)
            line.compute_amounts()
            inv.lines.append(line)
        inv.recalc_totals()
        self.session.add(inv)
        self.session.flush()

        ar = AccountsReceivable(
            customer_code=inv.customer_code,
            customer_name=inv.customer_name,
            sales_invoice_id=inv.id,
            invoice_number=inv.invoice_number,
            original_amount=inv.total_amount_with_tax,
            paid_amount=0,
            outstanding_amount=inv.total_amount_with_tax,
            invoice_date=inv.invoice_date,
            due_date=inv.due_date,
        )
        ar.refresh_overdue()
        self.session.add(ar)
        self.session.flush()
        return inv

    def create_purchase_invoice(self, header: dict, lines: list[dict]) -> PurchaseInvoice:
        """建立採購發票 + 明細，並開立對應應付帳款。"""
        if not lines:
            raise ValueError("發票至少需要一筆明細")
        inv = PurchaseInvoice(**header)
        for ld in lines:
            line = PurchaseTransaction(line_amount=0, **ld)
            line.compute_amounts()
            inv.lines.append(line)
        inv.recalc_totals()
        self.session.add(inv)
        self.session.flush()

        ap = AccountsPayable(
            supplier_code=inv.supplier_code,
            supplier_name=inv.supplier_name,
            purchase_invoice_id=inv.id,
            invoice_number=inv.invoice_number,
            original_amount=inv.total_amount_with_tax,
            paid_amount=0,
            outstanding_amount=inv.total_amount_with_tax,
            invoice_date=inv.invoice_date,
            due_date=inv.due_date,
        )
        ap.refresh_overdue()
        self.session.add(ap)
        self.session.flush()
        return inv

    # ------------------------------------------------------------ payments

    def record_payment(self, payment: dict) -> PaymentRecord:
        """記錄一筆收/付款並核銷對應發票與 AR/AP。

        payment: payment_number, payment_type (PaymentType 或字串),
                 transaction_date, reference_id (發票 id), amount,
                 payment_method, (optional) notes/...
        """
        ptype = payment.get("payment_type")
        if isinstance(ptype, str):
            ptype = PaymentType[ptype]
        amount = float(payment["amount"])
        if amount <= 0:
            raise ValueError("金額必須為正數")
        invoice_id = int(payment["reference_id"])

        if ptype == PaymentType.RECEIPT_FROM_CUSTOMER:
            inv = self.session.get(SalesInvoice, invoice_id)
            if inv is None:
                raise ValueError(f"找不到銷售發票 id={invoice_id}")
            party_code, party_name = inv.customer_code, inv.customer_name
            ledger = inv.receivable
        else:
            inv = self.session.get(PurchaseInvoice, invoice_id)
            if inv is None:
                raise ValueError(f"找不到採購發票 id={invoice_id}")
            party_code, party_name = inv.supplier_code, inv.supplier_name
            ledger = inv.payable

        outstanding = inv.total_amount_with_tax - (inv.paid_amount or 0)
        if amount > outstanding + 0.005:
            raise ValueError(f"金額 {amount} 超過未結餘額 {outstanding}")

        record = PaymentRecord(
            payment_number=payment["payment_number"],
            payment_type=ptype,
            transaction_date=payment.get("transaction_date") or date.today(),
            reference_type="INVOICE",
            reference_id=invoice_id,
            supplier_or_customer_code=party_code,
            supplier_or_customer_name=party_name,
            amount=amount,
            currency=payment.get("currency", inv.currency),
            payment_method=payment.get("payment_method", "TRANSFER"),
            bank_account_from=payment.get("bank_account_from"),
            bank_account_to=payment.get("bank_account_to"),
            check_number=payment.get("check_number"),
            transaction_reference=payment.get("transaction_reference"),
            notes=payment.get("notes"),
            created_by=payment.get("created_by", "system"),
        )
        self.session.add(record)

        inv.paid_amount = round((inv.paid_amount or 0) + amount, 2)
        inv.recalc_totals()
        if ledger is not None:
            ledger.paid_amount = inv.paid_amount
            ledger.outstanding_amount = inv.remaining_balance
            ledger.last_payment_date = record.transaction_date
            ledger.refresh_overdue()
        self.session.flush()
        return record

    # ------------------------------------------------------------- reports

    def daily_sales_report(self, report_date: date) -> dict:
        """日銷售報表 — 每張發票一列 + 合計。"""
        rows = []
        invoices = self.session.scalars(
            select(SalesInvoice)
            .where(SalesInvoice.invoice_date == report_date)
            .order_by(SalesInvoice.invoice_number)
        ).all()
        for inv in invoices:
            rows.append({
                "invoice_number": inv.invoice_number,
                "customer_code": inv.customer_code,
                "customer_name": inv.customer_name,
                "item_count": len(inv.lines),
                "total_pretax": inv.total_amount_pretax,
                "total_tax": inv.total_tax_amount,
                "total_withtax": inv.total_amount_with_tax,
                "gross_profit": round(sum(l.gross_profit or 0 for l in inv.lines), 2),
                "payment_status": inv.payment_status.value,
            })
        return {
            "date": report_date.isoformat(),
            "rows": rows,
            "totals": {
                "invoice_count": len(rows),
                "total_pretax": round(sum(r["total_pretax"] for r in rows), 2),
                "total_tax": round(sum(r["total_tax"] for r in rows), 2),
                "total_withtax": round(sum(r["total_withtax"] for r in rows), 2),
                "gross_profit": round(sum(r["gross_profit"] for r in rows), 2),
            },
        }

    def monthly_tax_summary(self, period: str, save: bool = False) -> dict:
        """月稅務彙總：應納稅額 = 銷項稅 − 進項稅。period 格式 YYYY-MM。

        save=True 時 upsert 一筆 TaxRecord（DRAFT 狀態）。
        """
        year, month = (int(x) for x in period.split("-"))
        start = date(year, month, 1)
        end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)

        s_amt, s_tax, s_cnt = self.session.execute(
            select(
                func.coalesce(func.sum(SalesInvoice.total_amount_pretax), 0),
                func.coalesce(func.sum(SalesInvoice.total_tax_amount), 0),
                func.count(SalesInvoice.id),
            ).where(SalesInvoice.invoice_date >= start,
                    SalesInvoice.invoice_date < end)
        ).one()
        p_amt, p_tax, p_cnt = self.session.execute(
            select(
                func.coalesce(func.sum(PurchaseInvoice.total_amount_pretax), 0),
                func.coalesce(func.sum(PurchaseInvoice.total_tax_amount), 0),
                func.count(PurchaseInvoice.id),
            ).where(PurchaseInvoice.invoice_date >= start,
                    PurchaseInvoice.invoice_date < end)
        ).one()

        summary = {
            "tax_period": period,
            "total_sales_amount": round(s_amt, 2),
            "total_sales_tax": round(s_tax, 2),
            "total_purchase_amount": round(p_amt, 2),
            "total_purchase_tax": round(p_tax, 2),
            "net_tax_payable": round(s_tax - p_tax, 2),
            "sales_invoice_count": s_cnt,
            "purchase_invoice_count": p_cnt,
        }

        if save:
            rec = self.session.scalars(
                select(TaxRecord).where(TaxRecord.tax_period == period,
                                        TaxRecord.tax_type == TaxType.VAT)
            ).first()
            if rec is None:
                rec = TaxRecord(tax_period=period, tax_type=TaxType.VAT)
                self.session.add(rec)
            elif rec.filing_status != FilingStatus.DRAFT:
                raise ValueError(f"{period} 已申報（{rec.filing_status.value}），不可覆寫")
            for k, v in summary.items():
                if k != "tax_period":
                    setattr(rec, k, v)
            self.session.flush()
        return summary

    def receivables(self, outstanding_only: bool = True) -> list[dict]:
        """應收帳款清單（含逾期天數，依到期日排序）。"""
        q = select(AccountsReceivable).order_by(AccountsReceivable.due_date)
        items = self.session.scalars(q).all()
        result = []
        for ar in items:
            ar.refresh_overdue()
            if outstanding_only and ar.outstanding_amount <= 0:
                continue
            result.append({
                "customer_code": ar.customer_code,
                "customer_name": ar.customer_name,
                "invoice_number": ar.invoice_number,
                "original_amount": ar.original_amount,
                "paid_amount": ar.paid_amount,
                "outstanding_amount": ar.outstanding_amount,
                "due_date": ar.due_date.isoformat(),
                "days_overdue": ar.days_overdue,
                "overdue_status": ar.overdue_status,
            })
        return result

    def payables(self, outstanding_only: bool = True) -> list[dict]:
        """應付帳款清單。"""
        q = select(AccountsPayable).order_by(AccountsPayable.due_date)
        items = self.session.scalars(q).all()
        result = []
        for ap in items:
            ap.refresh_overdue()
            if outstanding_only and ap.outstanding_amount <= 0:
                continue
            result.append({
                "supplier_code": ap.supplier_code,
                "supplier_name": ap.supplier_name,
                "invoice_number": ap.invoice_number,
                "original_amount": ap.original_amount,
                "paid_amount": ap.paid_amount,
                "outstanding_amount": ap.outstanding_amount,
                "due_date": ap.due_date.isoformat(),
                "days_overdue": ap.days_overdue,
                "overdue_status": ap.overdue_status,
            })
        return result
