from PyQt5.QtWidgets import (QMainWindow, QPushButton, QWidget, QVBoxLayout, 
                           QHBoxLayout, QLabel, QStackedWidget, QStatusBar,
                           QFrame, QGridLayout)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QIcon
from viewmodels.inventory_vm import InventoryViewModel
from views.dialogs.add_material_dialog import AddMaterialDialog

class FunctionCard(QFrame):
    """功能卡片元件"""
    def __init__(self, title: str, icon_path: str = None, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setup_ui(title, icon_path)
        
    def setup_ui(self, title: str, icon_path: str):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        # Icon (if provided)
        if icon_path:
            icon_label = QLabel()
            icon_label.setPixmap(QIcon(icon_path).pixmap(48, 48))
            layout.addWidget(icon_label, alignment=Qt.AlignCenter)
        
        # Title
        title_label = QLabel(title)
        title_label.setFont(QFont('Arial', 12, QFont.Bold))
        layout.addWidget(title_label, alignment=Qt.AlignCenter)
        
        self.setStyleSheet("""
            FunctionCard {
                background-color: white;
                border-radius: 8px;
                min-width: 150px;
                min-height: 120px;
            }
            FunctionCard:hover {
                background-color: #f0f0f0;
            }
        """)

class Homepage(QMainWindow):
    """首頁"""
    def __init__(self, session):
        super().__init__()
        self.session = session
        self.setup_viewmodels()
        self.setup_ui()
        self.setup_signals()

    def setup_viewmodels(self):
        """初始化 ViewModels"""
        self.inventory_vm = InventoryViewModel(self.session)

    def setup_ui(self):
        """設置UI"""
        # 設置主視窗
        self.setWindowTitle("Animal-AN-ERP System")
        self.setMinimumSize(1024, 768)

        # 創建中央視窗
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主佈局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # 頂部標題
        title_label = QLabel("Animal-AN-ERP 系統")
        title_label.setFont(QFont('Arial', 24, QFont.Bold))
        main_layout.addWidget(title_label, alignment=Qt.AlignTop)

        # 功能區域
        self.create_function_area(main_layout)

        # 設置狀態欄
        self.setup_status_bar()

    def create_function_area(self, parent_layout: QVBoxLayout):
        """創建功能區域"""
        # 功能區域容器
        function_widget = QWidget()
        function_layout = QGridLayout(function_widget)
        function_layout.setSpacing(20)

        # 定義功能卡片
        functions = [
            ("物料管理", "static/icons/material.png", self.show_material_management),
            ("庫存管理", "static/icons/inventory.png", self.show_inventory_management),
            ("訂單管理", "static/icons/order.png", self.show_order_management),
            ("生產管理", "static/icons/manufacturing.png", self.show_manufacturing_management)
        ]

        # 添加功能卡片到網格
        for idx, (title, icon_path, callback) in enumerate(functions):
            row, col = divmod(idx, 3)  # 每行3個卡片
            card = FunctionCard(title, icon_path)
            # 使卡片可點擊
            card.mousePressEvent = lambda _, f=callback: f()
            function_layout.addWidget(card, row, col)

        parent_layout.addWidget(function_widget)

    def setup_status_bar(self):
        """設置狀態欄"""
        status_bar = QStatusBar()
        status_bar.showMessage("系統就緒")
        self.setStatusBar(status_bar)

    def setup_signals(self):
        """設置信號連接"""
        pass

    def show_material_management(self):
        """顯示物料管理"""
        self.show_add_material_dialog()

    def show_inventory_management(self):
        """顯示庫存管理"""
        self.statusBar().showMessage("庫存管理功能開發中...")

    def show_order_management(self):
        """顯示訂單管理"""
        self.statusBar().showMessage("訂單管理功能開發中...")

    def show_manufacturing_management(self):
        """顯示生產管理"""
        self.statusBar().showMessage("生產管理功能開發中...")

    def show_add_material_dialog(self):
        """顯示新增物料對話框"""
        dialog = AddMaterialDialog(self.inventory_vm, self)
        dialog.materialAdded.connect(self.on_material_added)
        dialog.exec_()

    def on_material_added(self, material):
        """當物料新增成功時的處理"""
        self.statusBar().showMessage(f"新物料已添加: {material.code} - {material.name}", 5000)
