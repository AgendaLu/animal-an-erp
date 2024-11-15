from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QCalendarWidget, 
                            QTimeEdit, QLabel)
from PyQt5.QtCore import Qt, QTime, QDateTime
from PyQt5.QtGui import QKeyEvent

class DateTimePicker(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout(self)
        
        # Calendar widget
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self.calendar.setNavigationBarVisible(True)
        
        # Time edit widget
        time_layout = QHBoxLayout()
        time_label = QLabel("Time:")
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm:ss")
        self.time_edit.setTime(QTime.currentTime())
        self.time_edit.setCalendarPopup(True)
        
        time_layout.addWidget(time_label)
        time_layout.addWidget(self.time_edit)
        time_layout.addStretch()
        
        layout.addWidget(self.calendar)
        layout.addLayout(time_layout)
        
        # Enable keyboard focus
        self.setFocusPolicy(Qt.StrongFocus)
        self.calendar.setFocusPolicy(Qt.StrongFocus)
        self.time_edit.setFocusPolicy(Qt.StrongFocus)
        
    def keyPressEvent(self, event: QKeyEvent):
        if self.calendar.hasFocus():
            self._handleCalendarKeyPress(event)
        elif self.time_edit.hasFocus():
            self._handleTimeEditKeyPress(event)
        else:
            super().keyPressEvent(event)
            
    def _handleCalendarKeyPress(self, event: QKeyEvent):
        key = event.key()
        if key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            self.calendar.keyPressEvent(event)
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            self.time_edit.setFocus()
        else:
            super().keyPressEvent(event)
            
    def _handleTimeEditKeyPress(self, event: QKeyEvent):
        key = event.key()
        if key in (Qt.Key_Up, Qt.Key_Down):
            # Increment/decrement current section
            self.time_edit.stepBy(-1 if key == Qt.Key_Up else 1)
        elif key in (Qt.Key_Left, Qt.Key_Right):
            # Navigate between hour/minute/second
            self.time_edit.keyPressEvent(event)
        elif key.isdigit():
            # Allow direct number input
            self.time_edit.keyPressEvent(event)
        else:
            super().keyPressEvent(event)
            
    def getDateTime(self) -> QDateTime:
        """Get the selected date and time"""
        return QDateTime(self.calendar.selectedDate(), self.time_edit.time())
    
    def setDateTime(self, datetime: QDateTime):
        """Set the date and time"""
        self.calendar.setSelectedDate(datetime.date())
        self.time_edit.setTime(datetime.time())