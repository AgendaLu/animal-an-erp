"""
Custom message box component for consistent message display
"""
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import Qt

class MessageBox:
    """訊息對話框元件"""
    
    @staticmethod
    def information(title: str, message: str):
        """
        顯示信息對話框
        
        Args:
            title: 標題
            message: 訊息內容
        """
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.setDefaultButton(QMessageBox.Ok)
        return msg_box.exec_()

    @staticmethod
    def warning(title: str, message: str):
        """
        顯示警告對話框
        
        Args:
            title: 標題
            message: 警告內容
        """
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.setDefaultButton(QMessageBox.Ok)
        return msg_box.exec_()

    @staticmethod
    def error(title: str, message: str):
        """
        顯示錯誤對話框
        
        Args:
            title: 標題
            message: 錯誤內容
        """
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.setDefaultButton(QMessageBox.Ok)
        return msg_box.exec_()

    @staticmethod
    def confirm(title: str, message: str, default_button: QMessageBox.StandardButton = QMessageBox.No) -> bool:
        """
        顯示確認對話框
        
        Args:
            title: 標題
            message: 確認內容
            default_button: 預設按鈕
            
        Returns:
            bool: True if confirmed, False otherwise
        """
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Question)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setDefaultButton(default_button)
        
        # Set button text to Chinese
        msg_box.button(QMessageBox.Yes).setText('是')
        msg_box.button(QMessageBox.No).setText('否')
        
        return msg_box.exec_() == QMessageBox.Yes

    @staticmethod
    def custom(title: str, message: str, buttons: list, icon: QMessageBox.Icon = QMessageBox.Information):
        """
        顯示自定義對話框
        
        Args:
            title: 標題
            message: 內容
            buttons: 按鈕列表
            icon: 圖示類型
            
        Returns:
            QMessageBox.StandardButton: Clicked button
        """
        msg_box = QMessageBox()
        msg_box.setIcon(icon)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        
        # Add custom buttons
        for button in buttons:
            msg_box.addButton(button, QMessageBox.ActionRole)
            
        return msg_box.exec_()

class MessageBoxExample:
    """Message box usage examples"""
    
    @staticmethod
    def show_examples():
        message_box = MessageBox()
        
        # Information message
        message_box.information(
            "操作成功",
            "資料已成功儲存！"
        )
        
        # Warning message
        message_box.warning(
            "警告",
            "庫存量低於安全庫存！"
        )
        
        # Error message
        message_box.error(
            "錯誤",
            "無法連接資料庫！"
        )
        
        # Confirmation dialog
        if message_box.confirm(
            "確認刪除",
            "確定要刪除此筆資料嗎？\n此操作無法復原。"
        ):
            print("User confirmed deletion")
        else:
            print("User cancelled deletion")
        
        # Custom dialog
        buttons = [
            "儲存",
            "不儲存",
            "取消"
        ]
        result = message_box.custom(
            "未儲存的變更",
            "是否要儲存變更？",
            buttons,
            QMessageBox.Question
        )
        
        print(f"User clicked: {buttons[result]}")
