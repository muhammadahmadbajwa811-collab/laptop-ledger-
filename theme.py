"""Three-colour theme. Nothing else is used anywhere in the UI: no black, no white, no greys."""
import os
import tempfile

from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QColor, QPainter, QPen, QPixmap, QPolygon

LATTE = "#B7A89A"      # Cosmic Latte: page background, hover fills, separators
CREAM = "#E8DCC6"      # Mocha Cream: cards, inputs, table body
BURGUNDY = "#722F37"   # Deep Burgundy: sidebar, text, buttons, table header, accents

SANS = '"Segoe UI", "Inter", "Noto Sans", "DejaVu Sans", sans-serif'
SERIF = '"Georgia", "Noto Serif", "DejaVu Serif", serif'


def _arrow(path, color=BURGUNDY):
    pm = QPixmap(12, 8)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.NoPen)
    p.drawPolygon(QPolygon([QPoint(1, 1), QPoint(11, 1), QPoint(6, 7)]))
    p.end()
    pm.save(path, "PNG")


def _tick(path):
    pm = QPixmap(18, 18)
    pm.fill(QColor(BURGUNDY))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(CREAM), 2.4)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.drawPolyline(QPolygon([QPoint(4, 9), QPoint(8, 13), QPoint(14, 5)]))
    p.end()
    pm.save(path, "PNG")


def _dot(path):
    pm = QPixmap(18, 18)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(BURGUNDY), 1.5))
    p.setBrush(QColor(CREAM))
    p.drawEllipse(1, 1, 16, 16)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(BURGUNDY))
    p.drawEllipse(5, 5, 8, 8)
    p.end()
    pm.save(path, "PNG")


def stylesheet():
    tmp = tempfile.gettempdir()
    arrow, tick, dot = (os.path.join(tmp, n) for n in ("ledger_arrow.png", "ledger_tick.png", "ledger_dot.png"))
    _arrow(arrow)
    _tick(tick)
    _dot(dot)
    a, tk, dt = (p.replace("\\", "/") for p in (arrow, tick, dot))
    return f"""
* {{ font-family: {SANS}; font-size: 13px; color: {BURGUNDY}; outline: none; }}
QMainWindow, QDialog, QMessageBox, #page {{ background: {LATTE}; }}
QToolTip {{ background: {BURGUNDY}; color: {CREAM}; border: none; padding: 6px 8px; }}

/* sidebar */
#sidebar {{ background: {BURGUNDY}; }}
#sidebar QLabel {{ color: {CREAM}; background: transparent; }}
#brand {{ font-family: {SERIF}; font-size: 24px; font-weight: 700; }}
#brandSub {{ font-size: 12px; }}
QPushButton#nav {{ background: transparent; color: {CREAM}; text-align: left; padding: 12px 16px;
    border: none; border-radius: 10px; font-size: 14px; font-weight: 600; }}
QPushButton#nav:hover {{ background: {LATTE}; color: {BURGUNDY}; }}
QPushButton#nav:checked {{ background: {CREAM}; color: {BURGUNDY}; }}

/* headings and cards */
QLabel {{ background: transparent; }}
#title {{ font-family: {SERIF}; font-size: 28px; font-weight: 700; }}
#subtitle {{ font-size: 13px; }}
#section {{ font-family: {SERIF}; font-size: 17px; font-weight: 700; }}
#hint {{ font-size: 12px; }}
QFrame#card {{ background: {CREAM}; border-radius: 16px; }}
QFrame#tile {{ background: {BURGUNDY}; border-radius: 14px; }}
QFrame#tile QLabel {{ color: {CREAM}; }}
#tileValue {{ font-family: {SERIF}; font-size: 26px; font-weight: 700; }}
#tileLabel {{ font-size: 12px; }}
QFrame#banner {{ background: {CREAM}; border: 1.5px solid {BURGUNDY}; border-radius: 12px; }}

/* buttons */
QPushButton {{ background: {BURGUNDY}; color: {CREAM}; border: 1.5px solid {BURGUNDY}; border-radius: 10px;
    padding: 8px 18px; font-weight: 600; }}
QPushButton:hover {{ background: {LATTE}; color: {BURGUNDY}; }}
QPushButton:pressed {{ background: {CREAM}; color: {BURGUNDY}; }}
QPushButton:disabled {{ background: {LATTE}; color: {CREAM}; border-color: {LATTE}; }}
QPushButton#ghost {{ background: transparent; color: {BURGUNDY}; }}
QPushButton#ghost:hover {{ background: {LATTE}; }}
QPushButton#ghost:disabled {{ background: transparent; color: {LATTE}; border-color: {LATTE}; }}

/* inputs */
QLineEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{ background: {CREAM}; color: {BURGUNDY};
    border: 1.5px solid {BURGUNDY}; border-radius: 9px; padding: 6px 10px;
    selection-background-color: {BURGUNDY}; selection-color: {CREAM}; }}
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ background: {CREAM}; border: 2px solid {BURGUNDY}; padding: 5px 9px; }}
QLineEdit:disabled, QComboBox:disabled {{ background: {LATTE}; border-color: {LATTE}; }}
QComboBox {{ min-height: 20px; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{ image: url({a}); width: 12px; height: 8px; }}
QComboBox QAbstractItemView {{ background: {CREAM}; color: {BURGUNDY}; border: 1.5px solid {BURGUNDY};
    selection-background-color: {BURGUNDY}; selection-color: {CREAM}; padding: 4px; }}
QCheckBox, QRadioButton {{ spacing: 8px; background: transparent; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border: 1.5px solid {BURGUNDY}; border-radius: 5px; background: {CREAM}; }}
QCheckBox::indicator:checked {{ image: url({tk}); }}
QRadioButton::indicator {{ width: 18px; height: 18px; border: 1.5px solid {BURGUNDY}; border-radius: 10px; background: {CREAM}; }}
QRadioButton::indicator:checked {{ image: url({dt}); border: none; background: transparent; }}

QListWidget {{ background: {CREAM}; border: 1.5px solid {BURGUNDY}; border-radius: 9px; padding: 4px; }}
QListWidget::item {{ padding: 6px 8px; border-radius: 6px; }}
QListWidget::item:selected {{ background: {BURGUNDY}; color: {CREAM}; }}

QProgressBar {{ background: {LATTE}; border: none; border-radius: 8px; min-height: 16px; max-height: 16px; }}
QProgressBar::chunk {{ background: {BURGUNDY}; border-radius: 8px; }}

/* tables */
QTableView, QTableWidget {{ background: {CREAM}; color: {BURGUNDY}; gridline-color: {LATTE}; border: none;
    border-radius: 12px; selection-background-color: {BURGUNDY}; selection-color: {CREAM}; }}
QTableView::item {{ padding: 4px 10px; border-bottom: 1px solid {LATTE}; }}
QTableView::item:hover {{ background: {LATTE}; }}
QTableView::item:selected {{ background: {BURGUNDY}; color: {CREAM}; }}
QHeaderView {{ background: {BURGUNDY}; }}
QHeaderView::section {{ background: {BURGUNDY}; color: {CREAM}; padding: 10px 12px; border: none;
    border-right: 1px solid {LATTE}; font-weight: 700; }}
QHeaderView::section:hover {{ background: {LATTE}; color: {BURGUNDY}; }}
QHeaderView::up-arrow, QHeaderView::down-arrow {{ width: 10px; height: 10px; }}
QTableCornerButton::section {{ background: {BURGUNDY}; border: none; }}

/* scrollbars */
QScrollBar:vertical {{ background: {CREAM}; width: 12px; margin: 0; border-radius: 6px; }}
QScrollBar:horizontal {{ background: {CREAM}; height: 12px; margin: 0; border-radius: 6px; }}
QScrollBar::handle:vertical {{ background: {LATTE}; border-radius: 6px; min-height: 36px; }}
QScrollBar::handle:horizontal {{ background: {LATTE}; border-radius: 6px; min-width: 36px; }}
QScrollBar::handle:hover {{ background: {BURGUNDY}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollArea {{ border: none; background: transparent; }}
"""
