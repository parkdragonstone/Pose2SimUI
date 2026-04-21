"""
Startup crash diagnostics — run with: python diag.py
Prints each step so we can see exactly where SIGBUS occurs.
"""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))


def step(n, msg):
    print(f"[{n}] {msg}", flush=True)


step(0, "script started")

from PyQt6.QtWidgets import QApplication
step(1, "QApplication imported")

app = QApplication(sys.argv)
step(2, "QApplication created")

from PyQt6.QtGui import QFont
app.setFont(QFont("Arial", 12))
step(3, "font set (Arial)")

from src.utils.theme import QSS
step(4, "QSS string loaded")

app.setStyleSheet(QSS)
step(5, "stylesheet applied")

from src.ui.main_window import MainWindow
step(6, "MainWindow class imported")

w = MainWindow()
step(7, "MainWindow instance created")

w.show()
step(8, "window.show() called")

step(9, "entering event loop — app.exec()")
rc = app.exec()
step(10, f"event loop exited with {rc}")
sys.exit(rc)
