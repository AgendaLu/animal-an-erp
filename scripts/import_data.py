"""
CSV data import tool for Animal-AN ERP
Supports importing: suppliers, customers, products, materials, invoices, payments

Usage:
    python scripts/import_data.py <csv_dir>
    python scripts/import_data.py ./sample_data/
"""
import sys
import csv
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.database import db_manager
from models.partner import Supplier, Customer
from models.product import Product
from models.inventory import BulkItem
from models.accounting import SalesInvoice, SalesTransaction, PurchaseInvoice, PurchaseTransaction
from models.enums import SupplierType, CustomerType, ProductType, StorageType, PackageType
from utils.logger import get_logger

logger = get_logger(__name__)


class CSVImporter:
    """Import data from CSV files"""

    def __init__(self, csv_dir: Path):
        """Initialize importer with CSV directory"""
        self.csv_dir = Path(csv_dir)
        self.session = db_manager.get_session()
        self.import_stats = {
            'suppliers': 0,
            'customers': 0,
            'products': 0,
            'materials': 0,
            'sales_invoices': 0,
            'purchase_invoices': 0,
            'errors': []
        }

    def parse_csv(self, filepath: Path) -> List[Dict[str, Any]]:
        """Parse CSV file into list of dictionaries"""
        rows = []
        try:
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    logger.warning(f"Empty CSV file: {filepath}")
                    return rows

                for row_num, row in enumerate(reader, start=2):  # Start from 2 (after header)
                    if any(row.values()):  # Skip empty rows
                        rows.append(row)

            logger.info(f"Parsed {len(rows)} rows from {filepath.name}")
            return rows
        except Exception as e:
            logger.error(f"Error parsing CSV {filepath}: {e}")
            self.import_stats['errors'].append(f"CSV parse error in {filepath.name}: {e}")
            return rows

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date from string (support multiple formats)"""
        if not date_str or date_str.strip() == '':
            return None

        formats = [
            '%Y-%m-%d',
            '%Y/%m/%d',
            '%d-%m-%Y',
            '%d/%m/%Y',
            '%Y%m%d',
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue

        logger.warning(f"Could not parse date: {date_str}")
        return None

    def _parse_float(self, value: str) -> float:
        """Parse float value, handling different formats"""
        if not value or value.strip() == '':
            return 0.0
        try:
            return float(value.strip().replace(',', '.'))
        except ValueError:
            logger.warning(f"Could not parse float: {value}")
            return 0.0

    def _parse_bool(self, value: str) -> bool:
        """Parse boolean value"""
        if isinstance(value, bool):
            return value
        return str(value).lower() in ('true', '1', 'yes', 'y')

    def import_suppliers(self, csv_file: Optional[str] = None) -> int:
        """Import suppliers from CSV"""
        filename = csv_file or 'suppliers.csv'
        filepath = self.csv_dir / filename

        if not filepath.exists():
            logger.info(f"Suppliers CSV not found: {filepath}")
            return 0

        rows = self.parse_csv(filepath)
        count = 0

        for row in rows:
            try:
                # Check if supplier already exists
                existing = self.session.query(Supplier).filter_by(code=row.get('code')).first()
                if existing:
                    logger.debug(f"Supplier already exists: {row.get('code')}")
                    continue

                supplier_type_str = row.get('supplier_type', '').upper()
                supplier_type = SupplierType[supplier_type_str] if supplier_type_str else SupplierType.MANUFACTURER

                supplier = Supplier(
                    code=row.get('code'),
                    name=row.get('name'),
                    short_name=row.get('short_name', ''),
                    supplier_type=supplier_type,
                    country=row.get('country', ''),
                    contact_person=row.get('contact_person', ''),
                    phone=row.get('phone', ''),
                    email=row.get('email', ''),
                    address=row.get('address', ''),
                    credit_term_days=int(self._parse_float(row.get('credit_term_days', '0'))),
                    is_active=self._parse_bool(row.get('is_active', 'true'))
                )
                self.session.add(supplier)
                count += 1
            except Exception as e:
                logger.error(f"Error importing supplier {row.get('code')}: {e}")
                self.import_stats['errors'].append(f"Supplier import error ({row.get('code')}): {e}")

        self.session.commit()
        self.import_stats['suppliers'] = count
        logger.info(f"Imported {count} suppliers")
        return count

    def import_customers(self, csv_file: Optional[str] = None) -> int:
        """Import customers from CSV"""
        filename = csv_file or 'customers.csv'
        filepath = self.csv_dir / filename

        if not filepath.exists():
            logger.info(f"Customers CSV not found: {filepath}")
            return 0

        rows = self.parse_csv(filepath)
        count = 0

        for row in rows:
            try:
                # Check if customer already exists
                existing = self.session.query(Customer).filter_by(code=row.get('code')).first()
                if existing:
                    logger.debug(f"Customer already exists: {row.get('code')}")
                    continue

                customer_type_str = row.get('customer_type', '').upper()
                customer_type = CustomerType[customer_type_str] if customer_type_str else CustomerType.VET_CLINIC

                customer = Customer(
                    code=row.get('code'),
                    name=row.get('name'),
                    short_name=row.get('short_name', ''),
                    customer_type=customer_type,
                    contact_person=row.get('contact_person', ''),
                    phone=row.get('phone', ''),
                    email=row.get('email', ''),
                    address=row.get('address', ''),
                    credit_term_days=int(self._parse_float(row.get('credit_term_days', '0'))),
                    is_active=self._parse_bool(row.get('is_active', 'true'))
                )
                self.session.add(customer)
                count += 1
            except Exception as e:
                logger.error(f"Error importing customer {row.get('code')}: {e}")
                self.import_stats['errors'].append(f"Customer import error ({row.get('code')}): {e}")

        self.session.commit()
        self.import_stats['customers'] = count
        logger.info(f"Imported {count} customers")
        return count

    def import_products(self, csv_file: Optional[str] = None) -> int:
        """Import products (分裝品) from CSV"""
        filename = csv_file or 'products.csv'
        filepath = self.csv_dir / filename

        if not filepath.exists():
            logger.info(f"Products CSV not found: {filepath}")
            return 0

        rows = self.parse_csv(filepath)
        count = 0

        for row in rows:
            try:
                # Check if product already exists
                existing = self.session.query(Product).filter_by(code=row.get('code')).first()
                if existing:
                    logger.debug(f"Product already exists: {row.get('code')}")
                    continue

                product = Product(
                    code=row.get('code'),
                    name=row.get('name'),
                    product_type=ProductType[row.get('product_type', 'SUPPLEMENT')],
                    storage_type=StorageType[row.get('storage_type', 'ROOM_TEMP')],
                    package_type=PackageType[row.get('package_type', 'BOTTLE')],
                    unit=row.get('unit', ''),
                    selling_price=self._parse_float(row.get('selling_price', '0')),
                    spec=row.get('spec', ''),
                    manufacturer=row.get('manufacturer', ''),
                    description=row.get('description', ''),
                    is_active=self._parse_bool(row.get('is_active', 'true'))
                )
                self.session.add(product)
                count += 1
            except Exception as e:
                logger.error(f"Error importing product {row.get('code')}: {e}")
                self.import_stats['errors'].append(f"Product import error ({row.get('code')}): {e}")

        self.session.commit()
        self.import_stats['products'] = count
        logger.info(f"Imported {count} products")
        return count

    def import_materials(self, csv_file: Optional[str] = None) -> int:
        """Import materials (原裝品) from CSV"""
        filename = csv_file or 'materials.csv'
        filepath = self.csv_dir / filename

        if not filepath.exists():
            logger.info(f"Materials CSV not found: {filepath}")
            return 0

        rows = self.parse_csv(filepath)
        count = 0

        for row in rows:
            try:
                # Check if material already exists
                existing = self.session.query(BulkItem).filter_by(code=row.get('code')).first()
                if existing:
                    logger.debug(f"Material already exists: {row.get('code')}")
                    continue

                material = BulkItem(
                    code=row.get('code'),
                    name=row.get('name'),
                    description=row.get('description', ''),
                    unit=row.get('unit', ''),
                    quantity=self._parse_float(row.get('quantity', '0')),
                    min_quantity=self._parse_float(row.get('min_quantity', '0')),
                    product_type=ProductType[row.get('product_type', 'SUPPLEMENT')],
                    storage_type=StorageType[row.get('storage_type', 'ROOM_TEMP')],
                    is_active=self._parse_bool(row.get('is_active', 'true'))
                )
                self.session.add(material)
                count += 1
            except Exception as e:
                logger.error(f"Error importing material {row.get('code')}: {e}")
                self.import_stats['errors'].append(f"Material import error ({row.get('code')}): {e}")

        self.session.commit()
        self.import_stats['materials'] = count
        logger.info(f"Imported {count} materials")
        return count

    def run_import(self, order: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run import in specified order"""
        if order is None:
            order = ['suppliers', 'customers', 'materials', 'products']

        for entity_type in order:
            try:
                if entity_type == 'suppliers':
                    self.import_suppliers()
                elif entity_type == 'customers':
                    self.import_customers()
                elif entity_type == 'materials':
                    self.import_materials()
                elif entity_type == 'products':
                    self.import_products()
            except Exception as e:
                logger.error(f"Error during {entity_type} import: {e}")
                self.import_stats['errors'].append(f"{entity_type} import failed: {e}")

        return self.import_stats

    def print_summary(self):
        """Print import summary"""
        print("\n" + "=" * 70)
        print("IMPORT SUMMARY")
        print("=" * 70)
        print(f"Suppliers:        {self.import_stats['suppliers']}")
        print(f"Customers:        {self.import_stats['customers']}")
        print(f"Materials:        {self.import_stats['materials']}")
        print(f"Products:         {self.import_stats['products']}")
        print(f"Errors:           {len(self.import_stats['errors'])}")

        if self.import_stats['errors']:
            print("\nErrors:")
            for error in self.import_stats['errors'][:10]:  # Show first 10 errors
                print(f"  • {error}")
            if len(self.import_stats['errors']) > 10:
                print(f"  ... and {len(self.import_stats['errors']) - 10} more")

        print("=" * 70)


def main():
    """CLI entry point"""
    if len(sys.argv) < 2:
        print("Usage: python scripts/import_data.py <csv_dir>")
        print("\nExample:")
        print("  python scripts/import_data.py ./sample_data/")
        print("\nExpected CSV files in the directory:")
        print("  - suppliers.csv")
        print("  - customers.csv")
        print("  - materials.csv")
        print("  - products.csv")
        return 1

    csv_dir = Path(sys.argv[1])

    if not csv_dir.exists():
        print(f"Error: Directory not found: {csv_dir}")
        return 1

    # Initialize database
    try:
        db_manager.init_db()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return 1

    # Run import
    try:
        importer = CSVImporter(csv_dir)
        stats = importer.run_import()
        importer.print_summary()

        if stats['errors']:
            return 1  # Non-zero exit if there were errors
        return 0
    except Exception as e:
        logger.error(f"Import failed: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
