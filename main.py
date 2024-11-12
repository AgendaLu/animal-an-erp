"""
main.py: Application Entry Point
Initial version for testing database connection
"""

from pathlib import Path
from models.database import init_db, ItemType, Item

def setup_environment():
    """設定必要的目錄"""
    base_dir = Path(__file__).parent
    for dir_name in ['data', 'logs']:
        (base_dir / dir_name).mkdir(exist_ok=True)

def test_database():
    """測試資料庫連線和基本操作"""
    try:
        # 初始化資料庫
        session = init_db()
        
        # 測試新增一筆資料
        test_item = Item(
            name="測試商品",
            type=ItemType.FOOD,
            description="這是一個測試用商品",
            unit="包"
        )
        
        session.add(test_item)
        session.commit()
        
        print("資料庫測試成功！")
        print(f"已新增測試商品: {test_item.name}")
        
    except Exception as e:
        print(f"資料庫測試失敗: {str(e)}")

def main():
    """應用程式主入口"""
    setup_environment()
    test_database()

if __name__ == "__main__":
    main()