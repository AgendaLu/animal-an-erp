"""
Example of material input form using PyQt6
"""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QLabel, QLineEdit, 
                           QComboBox, QSpinBox, QDoubleSpinBox, 
                           QPushButton, QVBoxLayout, QHBoxLayout, 
                           QFormLayout, QMessageBox)
from PyQt6.QtCore import Qt

class MaterialInputForm(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        """Initialize the UI"""
        self.setWindowTitle('新增原料')
        self.setMinimumWidth(400)

        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Create form layout
        form_layout = QFormLayout()

        # Add form fields
        self.sku_input = QLineEdit()
        self.name_input = QLineEdit()
        self.unit_input = QComboBox()
        self.unit_input.addItems(['kg', 'g', 'L', 'mL', '包', '個'])
        
        self.amount_input = QDoubleSpinBox()
        self.amount_input.setRange(0, 999999)
        
        self.provider_input = QComboBox()
        self.provider_input.addItems(['供應商A', '供應商B'])  # Will be populated from database

        # Add fields to form
        form_layout.addRow('料號:', self.sku_input)
        form_layout.addRow('品名:', self.name_input)
        form_layout.addRow('單位:', self.unit_input)
        form_layout.addRow('數量:', self.amount_input)
        form_layout.addRow('供應商:', self.provider_input)

        # Add form to main layout
        layout.addLayout(form_layout)

        # Add buttons
        button_layout = QHBoxLayout()
        save_btn = QPushButton('儲存')
        save_btn.clicked.connect(self.save_material)
        cancel_btn = QPushButton('取消')
        cancel_btn.clicked.connect(self.close)

        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

    def save_material(self):
        """Save the material data"""
        # Here we'll add the actual save logic
        QMessageBox.information(self, '成功', '原料已儲存')