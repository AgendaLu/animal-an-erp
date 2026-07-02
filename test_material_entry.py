"""
Material Entry Form Test using PyQt5
"""

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QLabel, QLineEdit, QComboBox, 
                           QPushButton, QFormLayout, QSpinBox, QDoubleSpinBox)
from PyQt5.QtCore import Qt

class MaterialEntryForm(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        # Set window properties
        self.setWindowTitle('新增材料')
        self.setGeometry(100, 100, 400, 300)
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Create form layout
        form_layout = QFormLayout()
        
        # Create input fields
        self.name_input = QLineEdit()
        self.sku_input = QLineEdit()
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(['kg', 'g', 'L', 'mL', '包', '個'])
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0, 9999999)
        self.provider_input = QLineEdit()
        
        # Add fields to form
        form_layout.addRow('品名:', self.name_input)
        form_layout.addRow('料號:', self.sku_input)
        form_layout.addRow('單位:', self.unit_combo)
        form_layout.addRow('數量:', self.amount_spin)
        form_layout.addRow('供應商:', self.provider_input)
        
        # Add form to main layout
        main_layout.addLayout(form_layout)
        
        # Create buttons
        button_layout = QHBoxLayout()
        save_button = QPushButton('儲存')
        save_button.clicked.connect(self.save_clicked)
        cancel_button = QPushButton('取消')
        cancel_button.clicked.connect(self.close)
        
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout)
        
    def save_clicked(self):
        # Print the form data (for testing)
        print("材料資料:")
        print(f"品名: {self.name_input.text()}")
        print(f"料號: {self.sku_input.text()}")
        print(f"單位: {self.unit_combo.currentText()}")
        print(f"數量: {self.amount_spin.value()}")
        print(f"供應商: {self.provider_input.text()}")

# Create the application
app = QApplication.instance()
if app is None:
    app = QApplication([])

# Create and show the window
form = MaterialEntryForm()
form.show()

# Start the event loop
if __name__ == '__main__':
    app.exec_()