"""
main.py: Application Entry Point
"""

import sys
from pathlib import Path
from PyQt5.QtWidgets import QApplication
from models.database import init_db
from views.main_window import MainWindow

def setup_environment():
    """設定必要的目錄"""
    base_dir = Path(__file__).parent
    for dir_name in ['data', 'logs']:
        (base_dir / dir_name).mkdir(exist_ok=True)

def init_application():
    """初始化應用程式"""
    try:
        # 初始化資料庫
        session = init_db()
        return session
    except Exception as e:
        print(f"初始化失敗: {str(e)}")
        sys.exit(1)

def main():
    """應用程式主入口"""
    # 設定環境
    setup_environment()
    
    # 初始化資料庫
    session = init_application()
    
    # 創建 Qt 應用程式
    app = QApplication(sys.argv)
    
    # 創建並顯示主視窗
    window = MainWindow()
    window.show()
    
    # 執行應用程式
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()