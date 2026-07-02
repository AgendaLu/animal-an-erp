# views/main_window.py
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QFrame, QSizePolicy, QMenuBar,
    QStatusBar, QGridLayout, QSpacerItem, QMenu, QAction
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QIcon

class MainWindow(QMainWindow):
    """Main Window for the ERP System"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Animal-AN-ERP System")
        self.setMinimumSize(1200, 800)
        
        # Set the central widget and main layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Initialize UI components
        self._create_menubar()
        self._create_ui()
        self._create_statusbar()
        
    def _create_menubar(self):
        """Create the menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('檔案')
        
        # Add actions to file menu
        new_action = QAction('新增', self)
        new_action.setShortcut('Ctrl+N')
        file_menu.addAction(new_action)
        
        exit_action = QAction('離開', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu('編輯')
        
        # View menu
        view_menu = menubar.addMenu('檢視')
        
        # Help menu
        help_menu = menubar.addMenu('說明')
        
        about_action = QAction('關於', self)
        help_menu.addAction(about_action)
        
    def _create_ui(self):
        """Initialize the user interface"""
        # Create main content area
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # Add welcome section
        self._create_welcome_section(content_layout)
        
        # Add quick access buttons
        self._create_quick_access_section(content_layout)
        
        # Add main function grid
        self._create_main_functions(content_layout)
        
        self.main_layout.addWidget(content_widget)
        
    def _create_welcome_section(self, parent_layout):
        """Create the welcome section"""
        welcome_frame = QFrame()
        welcome_frame.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        welcome_layout = QVBoxLayout(welcome_frame)
        
        # Welcome message
        welcome_label = QLabel("歡迎使用 Animal-AN-ERP 系統")
        welcome_label.setFont(QFont("Arial", 24, QFont.Bold))
        welcome_label.setAlignment(Qt.AlignCenter)
        welcome_layout.addWidget(welcome_label)
        
        # Subtitle
        subtitle_label = QLabel("企業資源管理系統")
        subtitle_label.setFont(QFont("Arial", 14))
        subtitle_label.setAlignment(Qt.AlignCenter)
        welcome_layout.addWidget(subtitle_label)
        
        parent_layout.addWidget(welcome_frame)
        
    def _create_quick_access_section(self, parent_layout):
        """Create quick access buttons section"""
        quick_access_frame = QFrame()
        quick_access_layout = QHBoxLayout(quick_access_frame)
        
        # Quick access buttons
        buttons_data = [
            ("新增物料", self._on_add_material),
            ("製造流程", self._on_manufacture),
            ("庫存查詢", self._on_inventory_query),
            ("訂單管理", self._on_order_management)
        ]
        
        for text, callback in buttons_data:
            button = QPushButton(text)
            button.setMinimumSize(150, 50)
            button.setFont(QFont("Arial", 12))
            button.clicked.connect(callback)
            quick_access_layout.addWidget(button)
        
        parent_layout.addWidget(quick_access_frame)
        
    def _create_main_functions(self, parent_layout):
        """Create main functions grid"""
        functions_frame = QFrame()
        functions_frame.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        functions_layout = QGridLayout(functions_frame)
        
        # Main function cards
        functions_data = [
            ("庫存管理", "管理物料和產品庫存", self._on_inventory_management, 0, 0),
            ("生產管理", "管理生產排程和製造流程", self._on_production_management, 0, 1),
            ("採購管理", "管理供應商和採購訂單", self._on_procurement_management, 1, 0),
            ("銷售管理", "管理客戶和銷售訂單", self._on_sales_management, 1, 1)
        ]
        
        for title, desc, callback, row, col in functions_data:
            card = self._create_function_card(title, desc, callback)
            functions_layout.addWidget(card, row, col)
        
        parent_layout.addWidget(functions_frame)
        
    def _create_function_card(self, title, description, callback):
        """Create a function card widget"""
        card = QFrame()
        card.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        card.setMinimumSize(300, 200)
        
        layout = QVBoxLayout(card)
        
        # Title
        title_label = QLabel(title)
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Description
        desc_label = QLabel(description)
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # Button
        button = QPushButton("開啟")
        button.setMinimumSize(100, 40)
        button.clicked.connect(callback)
        layout.addWidget(button, alignment=Qt.AlignCenter)
        
        return card
        
    def _create_statusbar(self):
        """Create the status bar"""
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        status_bar.showMessage("系統就緒")
        
    # Event handlers
    def _on_add_material(self):
        """Handle add material button click"""
        self.statusBar().showMessage("開啟新增物料視窗...")
        # TODO: Implement material addition dialog
        
    def _on_manufacture(self):
        """Handle manufacture process button click"""
        self.statusBar().showMessage("開啟製造流程視窗...")
        # TODO: Implement manufacture process dialog
        
    def _on_inventory_query(self):
        """Handle inventory query button click"""
        self.statusBar().showMessage("開啟庫存查詢視窗...")
        # TODO: Implement inventory query dialog
        
    def _on_order_management(self):
        """Handle order management button click"""
        self.statusBar().showMessage("開啟訂單管理視窗...")
        # TODO: Implement order management dialog
        
    def _on_inventory_management(self):
        """Handle inventory management button click"""
        self.statusBar().showMessage("開啟庫存管理視窗...")
        # TODO: Implement inventory management window
        
    def _on_production_management(self):
        """Handle production management button click"""
        self.statusBar().showMessage("開啟生產管理視窗...")
        # TODO: Implement production management window
        
    def _on_procurement_management(self):
        """Handle procurement management button click"""
        self.statusBar().showMessage("開啟採購管理視窗...")
        # TODO: Implement procurement management window
        
    def _on_sales_management(self):
        """Handle sales management button click"""
        self.statusBar().showMessage("開啟銷售管理視窗...")
        # TODO: Implement sales management window