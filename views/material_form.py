"""
Material Entry Form implementation with database connection
"""

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                           QLabel, QLineEdit, QComboBox, QPushButton, 
                           QFormLayout, QDoubleSpinBox, QMessageBox)
from PyQt5.QtCore import Qt

class MaterialForm(QMainWindow):
    def __init__(self, inventory_manager):
        """Initialize the form with a database connection"""
        super().__init__()
        self.inventory_manager = inventory_manager
        self.init_ui()
        
    def init_ui(self):
        """Initialize the user interface"""
        # Set window properties
        self.setWindowTitle('新增材料')
        self.setGeometry(100, 100, 500, 400)
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Create form layout
        form_layout = QFormLayout()
        
        # Create input fields
        # SKU Input
        self.sku_input = QLineEdit()
        self.sku_input.setPlaceholderText('請輸入料號')
        
        # Name Input
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText('請輸入品名')
        
        # Unit Combo Box
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(['kg', 'g', 'L', 'mL', '包', '個', '箱'])
        
        # Amount Input
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0, 999999.99)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setValue(0.00)
        
        # Min Amount Input
        self.min_amount_spin = QDoubleSpinBox()
        self.min_amount_spin.setRange(0, 999999.99)
        self.min_amount_spin.setDecimals(2)
        self.min_amount_spin.setValue(0.00)
        
        # Provider Input
        self.provider_input = QLineEdit()
        self.provider_input.setPlaceholderText('請輸入供應商')
        
        # Notes Input
        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText('選填')
        
        # Add fields to form
        form_layout.addRow('料號 (*)', self.sku_input)
        form_layout.addRow('品名 (*)', self.name_input)
        form_layout.addRow('單位 (*)', self.unit_combo)
        form_layout.addRow('數量:', self.amount_spin)
        form_layout.addRow('安全庫存量:', self.min_amount_spin)
        form_layout.addRow('供應商 (*)', self.provider_input)
        form_layout.addRow('備註:', self.notes_input)
        
        # Add form to main layout
        main_layout.addLayout(form_layout)
        
        # Create buttons
        button_layout = QHBoxLayout()
        
        # Save Button
        self.save_button = QPushButton('儲存')
        self.save_button.clicked.connect(self.save_material)
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        # Cancel Button
        self.cancel_button = QPushButton('取消')
        self.cancel_button.clicked.connect(self.close)
        
        # Add buttons to layout
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        
        # Add some spacing before buttons
        main_layout.addSpacing(20)
        main_layout.addLayout(button_layout)
        
    def validate_inputs(self):
        """Validate all input fields"""
        if not self.sku_input.text().strip():
            QMessageBox.warning(self, '警告', '請輸入料號')
            return False
            
        if not self.name_input.text().strip():
            QMessageBox.warning(self, '警告', '請輸入品名')
            return False
            
        if not self.provider_input.text().strip():
            QMessageBox.warning(self, '警告', '請輸入供應商')
            return False
            
        return True
        
    def save_material(self):
        """Save material to database"""
        if not self.validate_inputs():
            return
            
        try:
            # Get values from inputs
            success, msg = self.inventory_manager.add_material(
                sku=self.sku_input.text().strip(),
                name=self.name_input.text().strip(),
                unit=self.unit_combo.currentText(),
                amount=self.amount_spin.value(),
                provider=self.provider_input.text().strip(),
                min_amount=self.min_amount_spin.value(),
                notes=self.notes_input.text().strip()
            )
            
            if success:
                QMessageBox.information(self, '成功', '材料新增成功！')
                self.clear_form()
            else:
                QMessageBox.warning(self, '錯誤', f'新增失敗: {msg}')
                
        except Exception as e:
            QMessageBox.critical(self, '錯誤', f'系統錯誤: {str(e)}')
            
    def clear_form(self):
        """Clear all input fields"""
        self.sku_input.clear()
        self.name_input.clear()
        self.unit_combo.setCurrentIndex(0)
        self.amount_spin.setValue(0)
        self.min_amount_spin.setValue(0)
        self.provider_input.clear()
        self.notes_input.clear()