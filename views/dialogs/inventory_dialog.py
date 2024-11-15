from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QComboBox, QSpinBox, QPushButton, QFormLayout)
from PyQt5.QtCore import Qt, QDateTime
from datetime import datetime
from models.database import Session
from models.inventory import Material, InventoryTransaction
from views.components.datetime_picker import DateTimePicker

class AddInventoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.session = Session()
        self.setupUI()
        self.loadMaterials()

    def setupUI(self):
        self.setWindowTitle("Add Inventory")
        layout = QFormLayout(self)

        # Material selection
        self.material_combo = QComboBox()
        layout.addRow("Material:", self.material_combo)

        # Amount input
        self.amount_spin = QSpinBox()
        self.amount_spin.setRange(1, 999999)
        layout.addRow("Amount:", self.amount_spin)

        # DateTime picker
        self.datetime_picker = DateTimePicker()
        self.datetime_picker.setDateTime(QDateTime.currentDateTime())
        layout.addRow("Date/Time:", self.datetime_picker)

        # Buttons
        button_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.cancel_btn = QPushButton("Cancel")
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addRow("", button_layout)

        # Connect signals
        self.save_btn.clicked.connect(self.saveInventory)
        self.cancel_btn.clicked.connect(self.reject)

    def loadMaterials(self):
        materials = self.session.query(Material).all()
        for material in materials:
            self.material_combo.addItem(material.name, material.id)

    def saveInventory(self):
        material_id = self.material_combo.currentData()
        amount = self.amount_spin.value()
        timestamp = self.datetime_picker.getDateTime().toPyDateTime()

        transaction = InventoryTransaction(
            material_id=material_id,
            amount=amount,
            timestamp=timestamp,
            transaction_type='IN'
        )

        try:
            self.session.add(transaction)
            self.session.commit()
            self.accept()
        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "Error", f"Failed to save: {str(e)}")

    def closeEvent(self, event):
        self.session.close()
        super().closeEvent(event)
