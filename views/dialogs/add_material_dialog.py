from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                           QLineEdit, QDoubleSpinBox, QPushButton, QFormLayout, 
                           QMessageBox, QTextEdit)
from PyQt5.QtCore import Qt, pyqtSignal
from viewmodels.inventory_vm import InventoryViewModel
from views.components.message_box import MessageBox

class AddMaterialDialog(QDialog):
    """新增物料對話框"""
    
    # 當物料新增成功時發出信號
    materialAdded = pyqtSignal(object)

    def __init__(self, inventory_vm: InventoryViewModel, parent=None):
        super().__init__(parent)
        self.inventory_vm = inventory_vm
        self.message_box = MessageBox()
        self.setup_ui()
        
    def setup_ui(self):
        """設置UI元件"""
        self.setWindowTitle("新增物料")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        # 主佈局
        main_layout = QVBoxLayout()
        
        # 表單佈局
        form_layout = self.create_form()
        main_layout.addLayout(form_layout)
        
        # 按鈕佈局
        button_layout = self.create_buttons()
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)

    def create_form(self) -> QFormLayout:
        """創建表單佈局"""
        form = QFormLayout()
        
        # 物料代碼
        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("M0000001")
        self.code_edit.setMaxLength(8)
        form.addRow("物料代碼*:", self.code_edit)
        
        # 物料名稱
        self.name_edit = QLineEdit()
        self.name_edit.setMaxLength(100)
        form.addRow("物料名稱*:", self.name_edit)
        
        # 描述
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(100)
        self.description_edit.setPlaceholderText("請輸入物料描述...")
        form.addRow("描述:", self.description_edit)
        
        # 單位
        self.unit_edit = QLineEdit()
        self.unit_edit.setPlaceholderText("例如：kg、個、箱")
        self.unit_edit.setMaxLength(20)
        form.addRow("單位*:", self.unit_edit)
        
        # 最小庫存量
        self.min_quantity_spin = QDoubleSpinBox()
        self.min_quantity_spin.setRange(0, 1000000)
        self.min_quantity_spin.setDecimals(2)
        self.min_quantity_spin.setSingleStep(1)
        form.addRow("最小庫存量:", self.min_quantity_spin)
        
        # 儲存溫度
        self.storage_temp_spin = QDoubleSpinBox()
        self.storage_temp_spin.setRange(-50, 50)
        self.storage_temp_spin.setValue(25)
        self.storage_temp_spin.setSuffix(" °C")
        form.addRow("儲存溫度:", self.storage_temp_spin)
        
        # 設置必填欄位標籤樣式
        for i in range(form.rowCount()):
            label_item = form.itemAt(i, QFormLayout.LabelRole)
            if label_item and "*:" in label_item.widget().text():
                label_item.widget().setStyleSheet("color: red")
        
        return form

    def create_buttons(self) -> QHBoxLayout:
        """創建按鈕佈局"""
        button_layout = QHBoxLayout()
        
        # 儲存按鈕
        self.save_button = QPushButton("儲存")
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self.save_material)
        
        # 取消按鈕
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        
        return button_layout

    def get_form_data(self) -> dict:
        """獲取表單數據"""
        return {
            'code': self.code_edit.text().strip(),
            'name': self.name_edit.text().strip(),
            'description': self.description_edit.toPlainText().strip(),
            'unit': self.unit_edit.text().strip(),
            'min_quantity': self.min_quantity_spin.value(),
            'storage_temp': self.storage_temp_spin.value()
        }

    def save_material(self):
        """儲存物料"""
        data = self.get_form_data()
        
        # 基本驗證
        if not data['code']:
            self.message_box.warning("錯誤", "請輸入物料代碼！")
            self.code_edit.setFocus()
            return
            
        if not data['name']:
            self.message_box.warning("錯誤", "請輸入物料名稱！")
            self.name_edit.setFocus()
            return
            
        if not data['unit']:
            self.message_box.warning("錯誤", "請輸入單位！")
            self.unit_edit.setFocus()
            return

        # 使用 ViewModel 儲存物料
        success, message, material = self.inventory_vm.create_material(data)
        
        if success:
            self.message_box.information("成功", "物料新增成功！")
            self.materialAdded.emit(material)  # 發出信號
            self.accept()
        else:
            self.message_box.warning("錯誤", message)
