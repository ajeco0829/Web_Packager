import os
import sys
import subprocess
import shutil
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget,
    QLabel, QListWidget, QAbstractItemView, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal

def get_assets_path():
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, "assets")

def find_first_html_file():
    assets_path = get_assets_path()
    for root, _, files in os.walk(assets_path):
        for file in files:
            if file.lower().endswith(".html"):
                return os.path.join(root, file)
    return None

def copy_files_with_structure(src_paths, dest_root):
    os.makedirs(dest_root, exist_ok=True)
    
    for src in src_paths:
        if os.path.isdir(src):
            for root, _, files in os.walk(src):
                for file in files:
                    rel_path = os.path.relpath(os.path.join(root, file), src)
                    dest_path = os.path.join(dest_root, os.path.basename(src), rel_path)
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    shutil.copy2(os.path.join(root, file), dest_path)
        else:
            dest_path = os.path.join(dest_root, os.path.basename(src))
            shutil.copy2(src, dest_path)

def create_generated_script():
    output_py = "generated_app.py"
    with open(output_py, "w", encoding="utf-8") as f:
        f.write(f'''
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl, Qt
import sys
import os

def get_assets_path():
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, "assets")

def find_first_html_file():
    assets_path = get_assets_path()
    for root, _, files in os.walk(assets_path):
        for file in files:
            if file.lower().endswith(".html"):
                return os.path.join(root, file)
    return None

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Generated Web App")
        self.setGeometry(100, 100, 900, 600)
        
        self.web_view = QWebEngineView()
        self.load_page()
        
        layout = QVBoxLayout()
        layout.addWidget(self.web_view)
        
        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
        
    def load_page(self):
        file_path = find_first_html_file()
        print("Trying to load:", file_path)
        if file_path and os.path.exists(file_path):
            self.web_view.setUrl(QUrl.fromLocalFile(file_path))
        else:
            self.web_view.setHtml("<h1>No HTML file found</h1>")

app = QApplication(sys.argv)
window = MainWindow()
window.show()
sys.exit(app.exec())
        ''')
    return output_py

class ConvertThread(QThread):
    finished = Signal(bool)

    def __init__(self, files):
        super().__init__()
        self.files = files

    def run(self):
        assets_folder = get_assets_path()
        copy_files_with_structure(self.files, assets_folder)
        output_py = create_generated_script()

        sep = ";" if sys.platform.startswith("win") else ":"
        pyinstaller_cmd = [
            "pyinstaller", "--onefile", "--windowed",
            "--add-data", f"{assets_folder}{sep}assets",
            "--name", "MyApp", output_py
        ]

        result = subprocess.run(pyinstaller_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print("Error:", result.stderr)
            self.finished.emit(False)
            return

        for item in [output_py, "MyApp.spec"]:
            if os.path.exists(item):
                os.remove(item)
        for folder in ["build"]:
            if os.path.exists(folder):
                shutil.rmtree(folder)

        self.finished.emit(True)

class FileDropWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Web_Packager")
        self.setGeometry(100, 100, 500, 400)
        self.setAcceptDrops(True)
        self.setStyleSheet("background-color: #ffe4e1;")

        self.central_widget = QWidget()
        self.layout = QVBoxLayout()

        self.label = QLabel("フォルダまたはファイルをドラッグ＆ドロップしてください")
        self.label.setAlignment(Qt.AlignCenter)

        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.file_list.setMinimumHeight(150)

        self.convert_button = QPushButton("変換")
        self.convert_button.setStyleSheet("background-color: #ffe4e1; border-radius: 5px;")
        self.convert_button.clicked.connect(self.convert_files)

        self.layout.addWidget(self.label)
        self.layout.addWidget(self.file_list)
        self.layout.addWidget(self.convert_button)

        self.central_widget.setLayout(self.layout)
        self.setCentralWidget(self.central_widget)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.isdir(file_path) or file_path.endswith((".html", ".css", ".js", ".png", ".jpg", ".jpeg")):
                if file_path not in [self.file_list.item(i).text() for i in range(self.file_list.count())]:
                    self.file_list.addItem(file_path)
        event.accept()

    def convert_files(self):
        self.convert_button.setDisabled(True)
        files = [self.file_list.item(i).text() for i in range(self.file_list.count())]
        if not files:
            QMessageBox.warning(self, "警告", "ファイルを追加してください。")
            self.convert_button.setDisabled(False)
            return

        self.thread = ConvertThread(files)
        self.thread.finished.connect(self.on_conversion_finished)
        self.thread.start()

    def on_conversion_finished(self, success):
        if success:
            QMessageBox.information(self, "成功", "変換が完了しました！")
            self.file_list.clear()
        else:
            QMessageBox.critical(self, "エラー", "変換に失敗しました。")

        self.convert_button.setDisabled(False)

def main():
    app = QApplication(sys.argv)
    window = FileDropWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
