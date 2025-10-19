import sys
import os
import subprocess
import json
import re
from datetime import datetime
import socket
import time
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTabWidget, QGridLayout, QLabel, QLineEdit,
    QTextEdit, QGroupBox, QRadioButton, QFrame, QScrollArea,
    QComboBox, QSizePolicy
)
from PySide6.QtCore import QProcess, Qt, QSize
from PySide6.QtGui import QMovie, QPixmap, QTextCursor

# Maps internal keys to display labels and tooltips (TODO in the future)
LABEL_MAPPING = {
    "salutation": ("Salutation:", "TODO: Anrede (Herr/Frau)"),
    "firstName": ("First Name:", "TODO: Your first name"),
    "lastName": "Last Name:", "emailAddress": "Email:", "phoneNumber": "Phone:",
    "street": "Street:", "houseNumber": "House Nr:", "postcode": "Postcode:", "city": "City:",
    "moveInDateType": "Move-in Date:", "numberOfPersons": "Household Size:",
    "employmentRelationship": "Employment:",
    "income": ("Income (Monthly Net):", "TODO: Select your net income range."),
    "applicationPackageCompleted": "Documents Ready:", "numberOfAdults": "Adults:",
    "numberOfKids": "Children:", "incomeAmount": "Exact Income (€):", "hasPets": "Pets:",
    "employmentStatus": "Contract Type:", "forCommercialPurposes": "Commercial Use:",
    "rentArrears": "Rent Arrears:", "insolvencyProcess": "Insolvency:", "smoker": "Smoker:",
}

# Default form data (keys must match LABEL_MAPPING)
DEFAULT_FORM_DATA = {
    "salutation": "Herr", "firstName": "John", "lastName": "Mustermann",
    "emailAddress": "john.mustermann@example.com", "phoneNumber": "+49999111111",
    "street": "Musterplatz", "houseNumber": "3", "postcode": "12345", "city": "Berlin",
    "moveInDateType": "ab sofort", "numberOfPersons": "Einpersonenhaushalt",
    "employmentRelationship": "Student:in", "income": "1.000 - 1.500 €",
    "applicationPackageCompleted": "Vorhanden", "numberOfAdults": "1",
    "numberOfKids": "0", "incomeAmount": "1.500", "hasPets": "Nein",
    "employmentStatus": "Unbefristet", "forCommercialPurposes": "Nein",
    "rentArrears": "Nein", "insolvencyProcess": "Nein", "smoker": "Nein",
}

DEFAULT_COVER_LETTER = """Sehr geehrte Damen und Herren, mein Name ist <firstName> <lastName>, ich bin 26 Jahre alt und studiere derzeit Informatik (M.Sc) an der TU Berlin. Ich arbeite als Werkstudent bei der Mustermedia, mit stabilem Einkommen und kann mir die Wohnung ohne Probleme leisten. Ich bin ruhig, zuverlässig, rauche nicht und habe keine Haustiere. Ich bin sehr an der Wohnung interessiert, da sie ideal zu meinen Vorstellungen von einem langfristigen und ruhigen Zuhause passt. Ich würde mich sehr über eine Rückmeldung und eine Einladung zur Besichtigung freuen. Mit freundlichen Grüßen <firstName> <lastName>"""

CONFIG_FILE = 'config.json'
RUNNER_SCRIPT = 'runner.py'

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Immo Bot Control Panel")
        self.setGeometry(100, 100, 800, 750)
        self.process = None
        self.form_widgets = {}

        self.load_config()

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.create_controls_tab()
        self.create_logs_tab()

        try:
            with open("style.qss", "r") as f: self.setStyleSheet(f.read())
        except FileNotFoundError: print("Warning: style.qss not found.")

        if not os.path.exists(CONFIG_FILE):
            print(f"'{CONFIG_FILE}' not found, creating a default one.")
            self.save_config()

    def create_controls_tab(self):
        tab_controls = QWidget()
        layout = QVBoxLayout(tab_controls)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        details_box = QGroupBox("User Details & Application")
        details_layout = self.create_filters_layout()
        details_box.setLayout(details_layout)
        scroll_area.setWidget(details_box)

        browser_box = QGroupBox("Browser Control")
        browser_layout = self.create_browser_layout()
        browser_box.setLayout(browser_layout)
        browser_box.setMaximumHeight(150)

        layout.addWidget(scroll_area)
        layout.addWidget(browser_box)
        self.tabs.addTab(tab_controls, "Controls")

    def create_filters_layout(self):
        layout = QVBoxLayout()
        grid_layout = QGridLayout()
        grid_layout.setColumnStretch(1, 1)
        grid_layout.setColumnStretch(3, 1)

        # --- NEW: Load info icon pixmap ---
        info_pixmap = QPixmap("assets/info.png")

        row, col = 0, 0
        for key, display_info in LABEL_MAPPING.items():
            if isinstance(display_info, tuple):
                display_text, tooltip_text = display_info
            else:
                display_text, tooltip_text = display_info, "TODO"

            label = QLabel(display_text)
            label.setObjectName("formLabel")
            
            # --- NEW: Use info.png for the info label ---
            info_label = QLabel()
            if not info_pixmap.isNull():
                info_label.setPixmap(info_pixmap.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else: # Fallback if image is missing
                info_label.setText("(?)")
            info_label.setToolTip(tooltip_text)

            # Use a widget to contain the layout for better styling
            label_container = QWidget()
            label_layout = QHBoxLayout(label_container)
            label_layout.setContentsMargins(0,0,0,0)
            label_layout.addWidget(label)
            label_layout.addWidget(info_label)
            label_container.setStyleSheet("background-color: transparent;")

            if key == "income":
                widget = QComboBox()
                widget.addItems(["unter 1.000 €", "1.000 - 1.500 €", "1.500 - 2.000 €", "2.000 - 2.500 €", "2.500 - 3.000 €", "über 3.000 €"])
                widget.setCurrentText(self.config['form_data'].get(key, ""))
            else:
                widget = QLineEdit(str(self.config['form_data'].get(key, "")))
            
            self.form_widgets[key] = widget
            grid_layout.addWidget(label_container, row, col * 2)
            grid_layout.addWidget(widget, row, col * 2 + 1)
            
            col = 1 - col
            if col == 0: row += 1

        layout.addLayout(grid_layout)
        layout.addWidget(QLabel("Cover Letter:"))
        self.cover_letter_widget = QTextEdit(self.config['cover_letter'])
        self.cover_letter_widget.setMinimumHeight(150)
        layout.addWidget(self.cover_letter_widget)

        btn_save = QPushButton("Save Details")
        btn_save.clicked.connect(self.save_config)
        layout.addWidget(btn_save, alignment=Qt.AlignRight)
        return layout

    def create_browser_layout(self):
        main_layout = QVBoxLayout()
        
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("Connect to:"))
        self.radio_buttons = {b: QRadioButton(b.capitalize()) for b in ["chrome", "edge", "firefox", "opera"]}
        for radio in self.radio_buttons.values():
            top_layout.addWidget(radio)
        self.radio_buttons["edge"].setChecked(True)
        top_layout.addStretch()
        
        launch_btn = QPushButton("Launch Selected Browser")
        launch_btn.clicked.connect(self.launch_selected_browser)
        top_layout.addWidget(launch_btn)

        bottom_layout = QHBoxLayout()
        self.btn_connect = QPushButton("Connect & Start Bot")
        self.btn_connect.setObjectName("ConnectButton")
        self.btn_connect.clicked.connect(self.run_bot)
        bottom_layout.addWidget(self.btn_connect)

        self.status_spinner = QLabel()
        self.status_spinner.setObjectName("statusSpinner") # For styling
        self.spinner_movie = QMovie("assets/spin.gif")
        self.spinner_movie.setScaledSize(QSize(25, 25))
        self.status_spinner.setMovie(self.spinner_movie)
        
        self.status_connected = QLabel("✔ Connected")
        self.status_connected.setObjectName("statusConnected")
        
        self.status_failed = QLabel("❌ Stopped")
        self.status_failed.setObjectName("statusFailed")

        bottom_layout.addWidget(self.status_spinner)
        bottom_layout.addWidget(self.status_connected)
        bottom_layout.addWidget(self.status_failed)
        bottom_layout.addStretch()
        self.set_status_indicator("idle")

        main_layout.addLayout(top_layout)
        main_layout.addLayout(bottom_layout)
        return main_layout

    # --- Logging helpers ---
    def log(self, message: str, level: str = "info"):
        """Append a formatted log line with timestamp and level."""
        colors = {
            "info": "#bbbbbb",
            "success": "#4CAF50",
            "warning": "#FFC107",
            "error": "#F44336",
            "debug": "#9E9E9E",
        }
        ts = datetime.now().strftime('%H:%M:%S')
        color = colors.get(level, colors["info"])
        level_text = level.upper()
        html = (
            f'<span style="color:#888">[{ts}]</span> '
            f'<span style="color:{color};font-weight:600">{level_text}:</span> '
            f'<span style="color:#ddd">{message}</span>'
        )
        # Append as HTML and autoscroll
        cursor = self.log_output.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_output.setTextCursor(cursor)
        self.log_output.insertHtml(html + "<br/>")
        self.log_output.ensureCursorVisible()

    def log_bot(self, message: str):
        """Append a subdued BOT line for raw process output."""
        ts = datetime.now().strftime('%H:%M:%S')
        safe = message.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        html = (
            f'<span style="color:#888">[{ts}]</span> '
            f'<span style="color:#9E9E9E;font-weight:600">BOT:</span> '
            f'<span style="color:#ccc">{safe}</span>'
        )
        cursor = self.log_output.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_output.setTextCursor(cursor)
        self.log_output.insertHtml(html + "<br/>")
        self.log_output.ensureCursorVisible()

    def set_status_indicator(self, state):
        states = {'connecting': (True, False, False), 'connected': (False, True, False),
                  'failed': (False, False, True), 'idle': (False, False, False)}
        spinner_visible, connected_visible, failed_visible = states.get(state, states['idle'])
        
        self.status_spinner.setVisible(spinner_visible)
        if spinner_visible: self.spinner_movie.start()
        else: self.spinner_movie.stop()
        
        self.status_connected.setVisible(connected_visible)
        self.status_failed.setVisible(failed_visible)

    def create_logs_tab(self):
        tab_logs = QWidget()
        layout = QVBoxLayout(tab_logs)
        self.log_output = QTextEdit(); self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)
        self.tabs.addTab(tab_logs, "Logs")

    def load_config(self):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f: self.config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.config = {'form_data': DEFAULT_FORM_DATA, 'cover_letter': DEFAULT_COVER_LETTER}

    def save_config(self):
        for key, widget in self.form_widgets.items():
            if isinstance(widget, QLineEdit): self.config['form_data'][key] = widget.text()
            elif isinstance(widget, QComboBox): self.config['form_data'][key] = widget.currentText()
        self.config['cover_letter'] = self.cover_letter_widget.toPlainText()
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f: json.dump(self.config, f, indent=4, ensure_ascii=False)
        print("Settings saved!")
    
    def launch_selected_browser(self):
        """NEW: Launches the browser that is currently selected by the radio button."""
        selected_browser = next((b for b, r in self.radio_buttons.items() if r.isChecked()), None)
        if selected_browser:
            self.launch_browser(selected_browser)
        else:
            self.log("Please select a browser to launch.", "warning")

    def _is_port_open(self, host: str, port: int, timeout: float = 0.5) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False

    def launch_browser(self, browser):
        self.log(f"Launching {browser.capitalize()} with remote debugging...", "info")
        username = os.getlogin()
        b = browser.lower()
        cmd = None
        if b == "chrome":
            candidates = [
                r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
                r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
                os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Google\\Chrome\\Application\\chrome.exe"),
            ]
            exe = next((p for p in candidates if p and os.path.exists(p)), None)
            if exe:
                cmd = f'& "{exe}" --remote-debugging-port=9222 --user-data-dir="C:\\temp\\immoscout_profile_{username}" --start-maximized --no-first-run --no-default-browser-check'
            else:
                self.log("Chrome executable not found. Please install Chrome or adjust path.", "error")
        elif b == "edge":
            candidates = [
                r"C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
                r"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
            ]
            exe = next((p for p in candidates if os.path.exists(p)), None)
            if exe:
                cmd = f'& "{exe}" --remote-debugging-port=9222 --user-data-dir="C:\\temp\\edge_profile_{username}" --start-maximized'
            else:
                self.log("Edge executable not found. Please install Edge or adjust path.", "error")
        elif b == "opera":
            exe = os.path.join(os.path.expanduser("~"), r"AppData\\Local\\Programs\\Opera\\launcher.exe")
            if os.path.exists(exe):
                cmd = f'& "{exe}" --remote-debugging-port=9222 --user-data-dir="C:\\temp\\opera_profile_{username}" --start-maximized'
            else:
                self.log("Opera executable not found.", "error")
        elif b == "firefox":
            candidates = [
                r"C:\\Program Files\\Mozilla Firefox\\firefox.exe",
                r"C:\\Program Files (x86)\\Mozilla Firefox\\firefox.exe",
            ]
            exe = next((p for p in candidates if os.path.exists(p)), None)
            if exe:
                cmd = f'& "{exe}" -marionette -start-debugger-server 2828'
            else:
                self.log("Firefox executable not found.", "error")

        if cmd:
            try:
                subprocess.Popen(["powershell", "-Command", cmd], creationflags=subprocess.CREATE_NO_WINDOW)
                self.log(f"Launch command for {browser.capitalize()} executed.", "debug")
                # Brief wait for port to open
                port = 2828 if b == "firefox" else 9222
                for _ in range(10):
                    if self._is_port_open("127.0.0.1", port):
                        break
                    time.sleep(0.3)
            except Exception as e:
                self.log(f"Failed to launch {browser}: {e}", "error")

    def run_bot(self):
        if self.process and self.process.state() == QProcess.Running:
            self.log("Stopping the bot...", "warning")
            self.process.kill(); return

        if not os.path.exists(RUNNER_SCRIPT):
            self.set_status_indicator("failed")
            self.log(f"FATAL: The script '{RUNNER_SCRIPT}' is missing.", "error"); return

        self.save_config()
        selected_browser = next((b for b, r in self.radio_buttons.items() if r.isChecked()), None)

        # Ensure the remote debugging port is open; auto-launch if needed
        port = 2828 if selected_browser == "firefox" else 9222
        if not self._is_port_open("127.0.0.1", port):
            self.log(f"Debug port {port} not open. Launching {selected_browser.capitalize()}...", "warning")
            self.launch_browser(selected_browser)
            # Wait up to ~10 seconds for port to open
            for i in range(20):
                time.sleep(0.5)
                if self._is_port_open("127.0.0.1", port):
                    break
            else:
                self.set_status_indicator("failed")
                self.log(
                    f"Could not detect {selected_browser.capitalize()} on debug port {port}. "
                    f"Please ensure no other instance is running and try again.",
                    "error",
                )
                return

        self.log_output.clear()
        self.log(f"Starting bot for {selected_browser.capitalize()}...", "info")
        self.set_status_indicator("connecting")
        self.btn_connect.setText("Stop Bot")
        self._bot_started_at = datetime.now()

        self.process = QProcess()
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.finished.connect(self.process_finished)
        self.process.start(sys.executable, [RUNNER_SCRIPT, selected_browser])

    def handle_stdout(self):
        data = self.process.readAllStandardOutput().data().decode(errors='ignore')
        for line in filter(None, (l.strip() for l in data.splitlines())):
            # Heuristic: map common phrases to nicer logs
            if "CONNECTED_OK" in line or "Successfully connected" in line:
                self.set_status_indicator("connected")
                self.log("Bot successfully connected.", "success")
            elif "Error connecting" in line or "FATAL" in line:
                self.set_status_indicator("failed")
                self.log(f"{line}", "error")
            else:
                self.log_bot(line)

    def process_finished(self):
        # Determine result based on status indicator visibility
        if self.status_connected.isVisible():
            self.set_status_indicator("idle")
            self.log("Bot finished successfully.", "success")
        else:
            self.set_status_indicator("failed")
            self.log("Bot stopped or failed.", "error")

        # Duration info
        try:
            started = getattr(self, "_bot_started_at", None)
            if started:
                elapsed = datetime.now() - started
                self.log(f"Run time: {elapsed}", "debug")
        except Exception:
            pass

        self.btn_connect.setText("Connect & Start Bot")
        self.process = None

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())