import sys
import os
import datetime
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QTabWidget, QListWidget, QListWidgetItem, 
                             QSystemTrayIcon, QMenu, QAction, QPushButton, QCheckBox)
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtCore import Qt, QTimer
import qdarkstyle

import database_manager

# Ensure DB is initialized
database_manager.init_db()

class JarvisApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Jarvis Dashboard")
        self.resize(800, 600)
        # Allow standard window controls so it can be maximized
        
        # We assume one main chat_id for now, or just show all.
        self.chat_id = "8895549195" # The chat ID from previous logs
        
        self.init_ui()
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(5000) # Refresh every 5 seconds
        
    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Header / Stats Dashboard
        header_layout = QHBoxLayout()
        
        self.title_label = QLabel("Jarvis Dashboard")
        self.title_label.setFont(QFont("Segoe UI", 18, QFont.Bold))
        header_layout.addWidget(self.title_label)
        
        header_layout.addStretch()
        
        self.stats_label = QLabel("API Requests Today: 0 / 100")
        self.stats_label.setFont(QFont("Segoe UI", 10))
        header_layout.addWidget(self.stats_label)
        
        from PyQt5.QtWidgets import QProgressBar
        self.api_progress = QProgressBar()
        self.api_progress.setMaximum(100)
        self.api_progress.setValue(0)
        self.api_progress.setFixedWidth(150)
        self.api_progress.setTextVisible(False)
        header_layout.addWidget(self.api_progress)
        
        main_layout.addLayout(header_layout)
        
        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setFont(QFont("Segoe UI", 11))
        
        # Common list stylesheet
        list_style = """
            QListWidget {
                border: none;
                background-color: #2b2b2b;
                border-radius: 8px;
                padding: 10px;
            }
            QListWidget::item {
                padding: 12px;
                border-bottom: 1px solid #3d3d3d;
                margin-bottom: 5px;
            }
            QListWidget::item:selected {
                background-color: #3d3d3d;
                border-radius: 5px;
            }
        """
        
        # To-Do Tab
        self.todo_tab = QWidget()
        self.todo_layout = QVBoxLayout()
        self.todo_list = QListWidget()
        self.todo_list.setStyleSheet(list_style)
        self.todo_list.setFont(QFont("Segoe UI", 10))
        self.todo_layout.addWidget(self.todo_list)
        self.todo_tab.setLayout(self.todo_layout)
        
        # Reminders Tab
        self.reminders_tab = QWidget()
        self.reminders_layout = QVBoxLayout()
        self.reminders_list = QListWidget()
        self.reminders_list.setStyleSheet(list_style)
        self.reminders_list.setFont(QFont("Segoe UI", 10))
        self.reminders_layout.addWidget(self.reminders_list)
        self.reminders_tab.setLayout(self.reminders_layout)
        
        self.tabs.addTab(self.todo_tab, "📝 To-Do List")
        self.tabs.addTab(self.reminders_tab, "⏰ Reminders")
        
        main_layout.addWidget(self.tabs)
        self.setLayout(main_layout)
        
        self.refresh_data()
        
    def refresh_data(self):
        # Update Stats
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        requests = database_manager.get_api_requests(today)
        self.stats_label.setText(f"API Requests Today: {requests} / 100")
        self.api_progress.setValue(min(requests, 100))
        if requests > 80:
            self.api_progress.setStyleSheet("QProgressBar::chunk { background-color: #e74c3c; }")
        else:
            self.api_progress.setStyleSheet("QProgressBar::chunk { background-color: #2ecc71; }")
        
        # Update To-Do
        tasks = database_manager.get_tasks(self.chat_id, "pending")
        self.todo_list.clear()
        for t in tasks:
            item = QListWidgetItem(f"🔴 [{t['deadline_iso'] or 'No deadline'}] {t['description']}")
            self.todo_list.addItem(item)
            
        # Update Reminders
        reminders = database_manager.get_reminders(self.chat_id)
        self.reminders_list.clear()
        for r in reminders:
            item = QListWidgetItem(f"🔔 [{r['remind_at_iso']}] {r['message']}")
            self.reminders_list.addItem(item)
            
    def closeEvent(self, event):
        event.ignore()
        self.hide()
        
class TrayIcon(QSystemTrayIcon):
    def __init__(self, app_widget, parent=None):
        # Use a default icon (can be replaced with a real icon file)
        icon = QIcon.fromTheme("system-run", QIcon("icon.png")) 
        super().__init__(icon, parent)
        self.app_widget = app_widget
        
        self.setToolTip("Jarvis")
        
        menu = QMenu()
        show_action = QAction("Show Dashboard", self)
        show_action.triggered.connect(self.show_dashboard)
        
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        
        menu.addAction(show_action)
        menu.addAction(quit_action)
        self.setContextMenu(menu)
        
        self.activated.connect(self.on_tray_click)
        
    def show_dashboard(self):
        self.app_widget.showNormal()
        self.app_widget.activateWindow()
        self.app_widget.raise_()
        
    def on_tray_click(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.show_dashboard()

def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
    app.setQuitOnLastWindowClosed(False)
    
    # Use absolute path for icon
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    icon_path = os.path.join(base_dir, "icon.png")
    
    if not os.path.exists(icon_path):
        from PyQt5.QtGui import QPixmap, QColor
        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor("blue"))
        pixmap.save(icon_path)
    
    jarvis_app = JarvisApp()
    
    tray = TrayIcon(jarvis_app)
    # Set the actual icon
    tray.setIcon(QIcon(icon_path))
    tray.show()
    
    # Show balloon tip
    tray.showMessage("Jarvis Dashboard", "I am running here in the background!", QSystemTrayIcon.Information, 3000)
    
    # Open window by default on startup
    jarvis_app.showNormal()
    jarvis_app.activateWindow()
    jarvis_app.raise_()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
