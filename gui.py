import os
import random
import threading

from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex, QThread, pyqtSignal
from PyQt5.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
                             QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
                             QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QRadioButton,
                             QSpinBox, QStackedWidget, QTableView, QTableWidget, QTableWidgetItem, QVBoxLayout,
                             QWidget)

import searching
import sorting
from parsers import COLUMNS, KEYS, KIND, LABEL, import_csv, load_csv, record_key, save_csv
from scraper import PRESETS, ScraperWorker

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "laptops.csv")


def fmt(v, key):
    if v is None or v == "":
        return "N/A"
    if KIND[key] == "num":
        if key == "rating":
            return f"{v:.1f}"
        return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.1f}"
    return str(v)


# ------------------------------------------------------------------ small helpers
def label(text, name=None, wrap=False):
    l = QLabel(text)
    if name:
        l.setObjectName(name)
    l.setWordWrap(wrap)
    return l


def card():
    f = QFrame()
    f.setObjectName("card")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(20, 18, 20, 18)
    lay.setSpacing(12)
    return f, lay


def page(title, subtitle):
    w = QWidget()
    w.setObjectName("page")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(30, 26, 30, 26)
    lay.setSpacing(14)
    lay.addWidget(label(title, "title"))
    lay.addWidget(label(subtitle, "subtitle", True))
    return w, lay


def tile(caption):
    f = QFrame()
    f.setObjectName("tile")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(18, 12, 18, 12)
    lay.setSpacing(0)
    value = label("-", "tileValue")
    lay.addWidget(value)
    lay.addWidget(label(caption, "tileLabel"))
    return f, value


def ghost(text):
    b = QPushButton(text)
    b.setObjectName("ghost")
    b.setCursor(Qt.PointingHandCursor)
    return b


def button(text):
    b = QPushButton(text)
    b.setCursor(Qt.PointingHandCursor)
    return b


def row(*widgets, stretch_last=False):
    h = QHBoxLayout()
    h.setSpacing(10)
    for w in widgets:
        if isinstance(w, int):
            h.addStretch(w)
        else:
            h.addWidget(w)
    return h


def info(parent, text):
    QMessageBox.information(parent, "Laptop Ledger", text)


def warn(parent, text):
    QMessageBox.warning(parent, "Laptop Ledger", text)


class Task(QThread):
    """Run a function off the UI thread. fn(task) may poll task.stop_flag and call task.note.emit(text)."""
    done = pyqtSignal(object)
    failed = pyqtSignal(str)
    note = pyqtSignal(str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self.fn = fn
        self.stop_flag = threading.Event()

    def run(self):
        try:
            self.done.emit(self.fn(self))
        except sorting.Cancelled:
            self.failed.emit("Cancelled")
        except Exception as e:
            self.failed.emit(f"{type(e).__name__}: {e}")


# ------------------------------------------------------------------ table model
class LaptopModel(QAbstractTableModel):
    def __init__(self, records):
        super().__init__()
        self.records = records       # shared list, only ever mutated in place
        self.view = []               # record indices in display order
        self.mark = None             # (column_index, descending) for the header arrow

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.view)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(COLUMNS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        key = KEYS[index.column()]
        if role == Qt.DisplayRole:
            return fmt(self.records[self.view[index.row()]].get(key), key)
        if role == Qt.TextAlignmentRole:
            return int((Qt.AlignRight if KIND[key] == "num" else Qt.AlignLeft) | Qt.AlignVCenter)
        if role == Qt.ToolTipRole and key in ("name", "url", "cpu"):
            return fmt(self.records[self.view[index.row()]].get(key), key)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            text = COLUMNS[section][1]
            if self.mark and self.mark[0] == section:
                text += "  ▼" if self.mark[1] else "  ▲"
            return text
        return None

    def set_view(self, view, mark=None):
        self.beginResetModel()
        self.view = view
        self.mark = mark
        self.endResetModel()

    def add_rows(self, idx):
        if idx:
            self.beginInsertRows(QModelIndex(), len(self.view), len(self.view) + len(idx) - 1)
            self.view.extend(idx)
            self.endInsertRows()


# ------------------------------------------------------------------ filter condition row
class ConditionRow(QWidget):
    removed = pyqtSignal(object)

    def __init__(self, first):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        self.conn = QComboBox()
        self.conn.addItems(["AND", "OR"])
        self.conn.setFixedWidth(76)
        self.where = label("Where")
        self.where.setFixedWidth(76)
        self.neg = QCheckBox("NOT")
        self.col = QComboBox()
        for key in KEYS:
            self.col.addItem(LABEL[key], key)
        self.op = QComboBox()
        self.v1 = QLineEdit()
        self.v2 = QLineEdit()
        self.v2.setPlaceholderText("and")
        self.algo = QComboBox()
        self.rm = ghost("✕")
        self.rm.setFixedWidth(40)
        self.rm.setToolTip("Remove this condition")
        self.col.setMinimumWidth(130)
        self.op.setMinimumWidth(120)
        self.algo.setMinimumWidth(170)
        self.v1.setMinimumWidth(150)
        h.addWidget(self.where if first else self.conn)
        for w in (self.neg, self.col, self.op, self.v1, self.v2, self.algo, self.rm):
            h.addWidget(w)
        h.setStretchFactor(self.v1, 2)
        self.rm.setVisible(not first)
        self.col.currentIndexChanged.connect(self._col_changed)
        self.op.currentIndexChanged.connect(self._op_changed)
        self.rm.clicked.connect(lambda: self.removed.emit(self))
        self._col_changed()

    def kind(self):
        return KIND[self.col.currentData()]

    def _col_changed(self):
        ops = searching.NUM_OPS if self.kind() == "num" else searching.STR_OPS
        self.op.blockSignals(True)
        self.op.clear()
        self.op.addItems(ops)
        self.op.blockSignals(False)
        self.v1.setPlaceholderText("e.g. 100000" if self.kind() == "num" else "e.g. dell")
        self._op_changed()

    def _op_changed(self):
        self.v2.setVisible(self.op.currentText() == "between")
        keep = self.algo.currentText()
        names = [a for a in searching.ALGOS if a == "Linear Search"
                 or searching.indexable(self.kind(), self.op.currentText(), a)]
        self.algo.clear()
        self.algo.addItems(names)
        if keep in names:
            self.algo.setCurrentText(keep)
        self.algo.setToolTip("Contains / ends with can only be answered by scanning, so Linear Search is used."
                             if names == ["Linear Search"] else "")

    def spec(self):
        return {"connector": self.conn.currentText(), "negate": self.neg.isChecked(), "col": self.col.currentData(),
                "kind": self.kind(), "op": self.op.currentText(), "v1": self.v1.text(), "v2": self.v2.text(),
                "algo": self.algo.currentText()}


# ------------------------------------------------------------------ benchmark dialog
class BenchmarkDialog(QDialog):
    def __init__(self, parent, items, column_label, scope_label):
        super().__init__(parent)
        self.items = items
        self.task = None
        self.setWindowTitle("Benchmark")
        self.resize(900, 600)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 22)
        lay.setSpacing(12)
        lay.addWidget(label("Benchmark", "title"))
        lay.addWidget(label(f"Every algorithm sorts the same data: column “{column_label}”, {scope_label}.", "subtitle", True))
        self.sample = QSpinBox()
        self.sample.setButtonSymbols(QSpinBox.NoButtons)
        self.sample.setRange(10, max(10, len(items)))
        self.sample.setValue(min(3000, max(10, len(items))))
        self.sample.setFixedWidth(100)
        self.all_rows = QCheckBox(f"Use all {len(items):,} rows (slow algorithms can take minutes)")
        self.run_btn = button("Run benchmark")
        self.stop_btn = ghost("Stop")
        self.stop_btn.setEnabled(False)
        lay.addLayout(row(label("Sample size"), self.sample, self.all_rows, 1, self.stop_btn, self.run_btn))
        self.status = label("", "hint")
        lay.addWidget(self.status)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Algorithm", "Average", "Worst", "Stable", "Time (ms)", "Comparisons", "Swaps"])
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for c in range(1, 7):
            self.table.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeToContents)
        lay.addWidget(self.table, 1)
        close = ghost("Close")
        close.clicked.connect(self.close)
        lay.addLayout(row(1, close))
        self.run_btn.clicked.connect(self.run)
        self.stop_btn.clicked.connect(lambda: self.task and self.task.stop_flag.set())

    def run(self):
        n = len(self.items) if self.all_rows.isChecked() else min(self.sample.value(), len(self.items))
        data = self.items if n == len(self.items) else random.Random(7).sample(self.items, n)
        self.table.setRowCount(0)

        def job(task):
            out = []
            for name in sorting.ALGORITHMS:
                if task.stop_flag.is_set():
                    break
                task.note.emit(f"Running {name} on {n:,} rows…")
                _, st, ms = sorting.run_sort(name, data, task.stop_flag)
                out.append((name, ms, st.comparisons, st.swaps))
                task.done_partial = out
            return out
        self.task = Task(job, self)
        self.task.note.connect(self.status.setText)
        self.task.done.connect(self._done)
        self.task.failed.connect(self._failed)
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.task.start()

    def _finish(self):
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def _failed(self, msg):
        self._finish()
        self.status.setText("Stopped. " + ("Results so far are shown." if msg == "Cancelled" else msg))
        self._fill(getattr(self.task, "done_partial", []))

    def _done(self, results):
        self._finish()
        self.status.setText("Done. The fastest algorithm is highlighted.")
        self._fill(results)

    def _fill(self, results):
        self.table.setRowCount(len(results))
        fastest = min((r[1] for r in results), default=None)
        for r, (name, ms, c, s) in enumerate(results):
            _, avg, worst, stable = sorting.ALGORITHMS[name]
            vals = [name, avg, worst, "Yes" if stable else "No", f"{ms:,.2f}", f"{c:,}", f"{s:,}"]
            for col, v in enumerate(vals):
                it = QTableWidgetItem(v)
                it.setTextAlignment(int((Qt.AlignRight if col >= 4 else Qt.AlignLeft) | Qt.AlignVCenter))
                self.table.setItem(r, col, it)
            if ms == fastest:
                self.table.selectRow(r)

    def closeEvent(self, e):
        if self.task and self.task.isRunning():
            self.task.stop_flag.set()
            self.task.wait(3000)
        super().closeEvent(e)


# ------------------------------------------------------------------ main window
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Laptop Ledger")
        self.resize(1360, 820)
        self.setMinimumSize(1100, 700)
        self.records = []
        self.order = []             # every record index in the current "full" order
        self.fset = None            # set of record indices passing the filter, or None
        self.filter_text = ""
        self.cache = searching.IndexCache()
        self.model = LaptopModel(self.records)
        self.col_algo = {}
        self.sort_col, self.sort_desc = None, False
        self.worker = None
        self.task = None
        self.batches = 0
        self.scope_radios = []

        root = QWidget()
        self.setCentralWidget(root)
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        h.addWidget(self._build_sidebar())
        self.stack = QStackedWidget()
        h.addWidget(self.stack, 1)
        for p in (self._build_collect(), self._build_laptops(), self._build_filters(), self._build_multisort()):
            self.stack.addWidget(p)
        self.go(0)
        self._load_saved()

    # ---------------------------------------------------------------- sidebar
    def _build_sidebar(self):
        bar = QFrame()
        bar.setObjectName("sidebar")
        bar.setFixedWidth(230)
        lay = QVBoxLayout(bar)
        lay.setContentsMargins(18, 26, 18, 22)
        lay.setSpacing(6)
        lay.addWidget(label("Laptop Ledger", "brand"))
        lay.addWidget(label("CS200 · Data Structures & Algorithms", "brandSub", True))
        lay.addSpacing(26)
        self.nav = []
        for i, text in enumerate(["Collect", "Laptops", "Search and filters", "Multi-level sort"]):
            b = QPushButton(text)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _, i=i: self.go(i))
            lay.addWidget(b)
            self.nav.append(b)
        lay.addStretch(1)
        self.side_count = label("0 laptops", "brandSub")
        lay.addWidget(self.side_count)
        return bar

    def go(self, i):
        self.stack.setCurrentIndex(i)
        for k, b in enumerate(self.nav):
            b.setChecked(k == i)

    # ---------------------------------------------------------------- collect page
    def _build_collect(self):
        w, lay = page("Collect laptops", "Paste a listing page URL, add it to the queue, then start. "
                      "Scraping runs in the background; pause, resume or stop whenever you like.")
        c1, l1 = card()
        l1.addWidget(label("Pages to scrape", "section"))
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://shop.example.pk/laptops")
        add = button("Add URL")
        add.clicked.connect(self.add_url)
        self.url_edit.returnPressed.connect(self.add_url)
        l1.addLayout(row(self.url_edit, add))
        presets = [label("Quick add:", "hint")]
        for name, url in PRESETS.items():
            b = ghost(name)
            b.clicked.connect(lambda _, u=url: self.add_url(u))
            presets.append(b)
        presets.append(1)
        l1.addLayout(row(*presets))
        self.queue = QListWidget()
        self.queue.setFixedHeight(96)
        l1.addWidget(self.queue)
        rm, clr = ghost("Remove selected"), ghost("Clear queue")
        rm.clicked.connect(lambda: [self.queue.takeItem(self.queue.row(i)) for i in self.queue.selectedItems()])
        clr.clicked.connect(self.queue.clear)
        l1.addLayout(row(rm, clr, 1))
        lay.addWidget(c1)

        c2, l2 = card()
        l2.addWidget(label("Run", "section"))
        self.target = QSpinBox()
        self.target.setRange(100, 1_000_000)
        self.target.setValue(15000)
        self.target.setButtonSymbols(QSpinBox.NoButtons)
        self.target.setFixedWidth(100)
        self.delay = QDoubleSpinBox()
        self.delay.setRange(0.0, 30.0)
        self.delay.setValue(1.0)
        self.delay.setSingleStep(0.5)
        self.delay.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.delay.setFixedWidth(70)
        self.robots = QCheckBox("Respect robots.txt")
        self.robots.setChecked(True)
        l2.addLayout(row(label("Target laptops"), self.target, label("Delay between pages (s)"), self.delay, self.robots, 1))
        self.btn_start, self.btn_pause = button("Start"), ghost("Pause")
        self.btn_resume, self.btn_stop = ghost("Resume"), ghost("Stop")
        self.btn_start.clicked.connect(self.start_scrape)
        self.btn_pause.clicked.connect(lambda: (self.worker.pause(), self._scrape_state("paused")))
        self.btn_resume.clicked.connect(lambda: (self.worker.resume(), self._scrape_state("running")))
        self.btn_stop.clicked.connect(lambda: self.worker.stop())
        imp, exp = ghost("Import CSV"), ghost("Export CSV")
        imp.clicked.connect(self.import_file)
        exp.clicked.connect(self.export_file)
        clr_data = ghost("Clear data")
        clr_data.clicked.connect(self.clear_data)
        l2.addLayout(row(self.btn_start, self.btn_pause, self.btn_resume, self.btn_stop, 1, imp, exp, clr_data))
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar_label = label("0 / 15,000 laptops", "hint")
        l2.addLayout(row(self.bar, self.bar_label))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        l2.addWidget(self.log, 1)
        lay.addWidget(c2, 1)
        self.target.valueChanged.connect(self._update_progress)
        self._scrape_state("idle")
        return w

    def add_url(self, url=None):
        url = url if isinstance(url, str) else self.url_edit.text()
        url = url.strip()
        if not url:
            return
        if not url.startswith("http"):
            url = "https://" + url
        if url not in [self.queue.item(i).text() for i in range(self.queue.count())]:
            self.queue.addItem(url)
        self.url_edit.clear()

    def _scrape_state(self, state):
        self.btn_start.setEnabled(state == "idle")
        self.btn_pause.setEnabled(state == "running")
        self.btn_resume.setEnabled(state == "paused")
        self.btn_stop.setEnabled(state in ("running", "paused"))

    def start_scrape(self):
        self.add_url()
        seeds = [self.queue.item(i).text() for i in range(self.queue.count())]
        if not seeds:
            return warn(self, "Add at least one listing URL first.")
        self.worker = ScraperWorker(seeds, self.target.value(), self.delay.value(), {record_key(r) for r in self.records},
                                    len(self.records), self.robots.isChecked(), self)
        self.worker.batch.connect(self.add_records)
        self.worker.log.connect(self.log.appendPlainText)
        self.worker.finished_with.connect(self._scrape_done)
        self.batches = 0
        self._scrape_state("running")
        self.worker.start()

    def _scrape_done(self, reason):
        self.log.appendPlainText(reason)
        self._scrape_state("idle")
        self._autosave()

    def _update_progress(self):
        t, n = self.target.value(), len(self.records)
        self.bar.setRange(0, t)
        self.bar.setValue(min(n, t))
        self.bar_label.setText(f"{n:,} / {t:,} laptops")

    def _autosave(self):
        os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
        save_csv(DATA_PATH, self.records)

    def _load_saved(self):
        if os.path.exists(DATA_PATH):
            try:
                self.add_records(load_csv(DATA_PATH))
            except Exception as e:
                self.log.appendPlainText(f"Could not load saved data: {e}")

    def add_records(self, new):
        base = len(self.records)
        self.records.extend(new)
        idx = list(range(base, base + len(new)))
        self.order.extend(idx)
        self.cache.clear()
        if self.fset is None:
            self.model.add_rows(idx)
        self._refresh_counts()
        self.batches += 1
        if self.worker and self.worker.isRunning() and self.batches % 10 == 0:
            self._autosave()

    def _refresh_counts(self):
        n, shown = len(self.records), len(self.model.view)
        self.side_count.setText(f"{n:,} laptops")
        self.count_label.setText(f"{shown:,} shown of {n:,}")
        self._update_progress()

    def import_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import laptop CSV", "", "CSV files (*.csv)")
        if not path:
            return
        try:
            recs = import_csv(path)
        except Exception as e:
            return warn(self, f"Could not read that file: {e}")
        known = {record_key(r) for r in self.records}
        fresh = [r for r in recs if record_key(r) not in known]
        self.add_records(fresh)
        self.log.appendPlainText(f"Imported {len(fresh):,} laptops from {os.path.basename(path)} ({len(recs) - len(fresh):,} duplicates skipped).")
        self._autosave()

    def clear_data(self):
        if self.worker and self.worker.isRunning():
            return warn(self, "Stop the scraper first.")
        ans = QMessageBox.question(self, "Laptop Ledger", "Delete all scraped laptops? This cannot be undone.")
        if ans != QMessageBox.Yes:
            return
        self.records.clear()
        self.order.clear()
        self.fset = None
        self.cache.clear()
        self.banner.hide()
        self.model.set_view([])
        if os.path.exists(DATA_PATH):
            os.remove(DATA_PATH)
        self._refresh_counts()
        self.log.appendPlainText("All data cleared.")

    def export_file(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export shown laptops", "laptops.csv", "CSV files (*.csv)")
        if path:
            save_csv(path, [self.records[i] for i in self.model.view])
            self.log.appendPlainText(f"Exported {len(self.model.view):,} rows to {path}")

    # ---------------------------------------------------------------- laptops page
    def _scope_widget(self):
        full, filt = QRadioButton("Full dataset"), QRadioButton("Filtered results only")
        full.setChecked(True)
        self.scope_radios.append((full, filt))
        for me in (full, filt):
            me.toggled.connect(self._sync_scope)
        box = QWidget()
        box.setLayout(row(full, filt))
        box.layout().setContentsMargins(0, 0, 0, 0)
        return box

    def _sync_scope(self, _):
        sender = self.sender()
        want_full = sender.text() == "Full dataset" and sender.isChecked() or sender.text() != "Full dataset" and not sender.isChecked()
        for full, filt in self.scope_radios:
            for r, state in ((full, want_full), (filt, not want_full)):
                r.blockSignals(True)
                r.setChecked(state)
                r.blockSignals(False)

    def scope_full(self):
        return self.scope_radios[0][0].isChecked()

    def _algo_combo(self):
        c = QComboBox()
        c.addItems(list(sorting.ALGORITHMS))
        c.setCurrentText("Merge Sort")
        c.setMinimumWidth(190)
        return c

    def _build_laptops(self):
        w, lay = page("Laptops", "Click a column header to sort it with the selected algorithm, or use the controls below.")
        self.count_label = label("0 shown of 0", "hint")
        c, cl = card()
        self.sort_col_box = QComboBox()
        for key in KEYS:
            self.sort_col_box.addItem(LABEL[key], key)
        self.sort_algo = self._algo_combo()
        self.sort_order = QComboBox()
        self.sort_order.addItems(["Ascending", "Descending"])
        self.btn_sort, self.btn_bench = button("Sort"), ghost("Benchmark")
        self.btn_cancel = ghost("Cancel")
        self.btn_cancel.hide()
        cl.addLayout(row(label("Column"), self.sort_col_box, label("Algorithm"), self.sort_algo, self.sort_order,
                         1, self.btn_cancel, self.btn_bench, self.btn_sort))
        self.algo_info = label("", "hint")
        cl.addLayout(row(self._scope_widget(), 1, self.algo_info))
        lay.addWidget(c)

        tiles = QHBoxLayout()
        tiles.setSpacing(12)
        self.tiles = {}
        for key, cap in (("ms", "Time (milliseconds)"), ("cmp", "Comparisons"), ("swp", "Swaps"), ("n", "Rows sorted")):
            t, v = tile(cap)
            self.tiles[key] = v
            tiles.addWidget(t)
        lay.addLayout(tiles)

        self.banner = QFrame()
        self.banner.setObjectName("banner")
        bl = QHBoxLayout(self.banner)
        bl.setContentsMargins(16, 8, 10, 8)
        self.banner_text = label("")
        clear = ghost("Clear filter")
        clear.clicked.connect(self.clear_filters)
        bl.addWidget(self.banner_text, 1)
        bl.addWidget(clear)
        self.banner.hide()
        lay.addWidget(self.banner)

        top = QHBoxLayout()
        top.addWidget(self.count_label)
        top.addStretch(1)
        lay.addLayout(top)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        hdr = self.table.horizontalHeader()
        hdr.setSectionsClickable(True)
        hdr.setHighlightSections(False)
        hdr.setSectionResizeMode(QHeaderView.Interactive)
        hdr.setStretchLastSection(True)
        for i, wd in enumerate([330, 95, 110, 80, 100, 170, 110, 135, 120, 130, 110, 260]):
            self.table.setColumnWidth(i, wd)
        hdr.sectionClicked.connect(self.header_clicked)
        lay.addWidget(self.table, 1)

        self.sort_col_box.currentIndexChanged.connect(self._col_algo_load)
        self.sort_algo.currentTextChanged.connect(self._algo_changed)
        self.btn_sort.clicked.connect(lambda: self.start_sort([(self.sort_col_box.currentData(), self.sort_order.currentIndex() == 1)],
                                                              self.sort_algo.currentText()))
        self.btn_bench.clicked.connect(self.open_benchmark)
        self.btn_cancel.clicked.connect(lambda: self.task and self.task.stop_flag.set())
        self._algo_changed(self.sort_algo.currentText())
        return w

    def _algo_changed(self, name):
        self.col_algo[self.sort_col_box.currentData()] = name
        self.algo_info.setText(sorting.describe(name))

    def _col_algo_load(self):
        name = self.col_algo.get(self.sort_col_box.currentData(), "Merge Sort")
        self.sort_algo.blockSignals(True)
        self.sort_algo.setCurrentText(name)
        self.sort_algo.blockSignals(False)
        self.algo_info.setText(sorting.describe(name))

    def header_clicked(self, i):
        key = KEYS[i]
        self.sort_desc = (not self.sort_desc) if self.sort_col == key else False
        self.sort_col_box.setCurrentIndex(i)
        self.sort_order.setCurrentIndex(1 if self.sort_desc else 0)
        self.start_sort([(key, self.sort_desc)], self.sort_algo.currentText())

    # ---------------------------------------------------------------- sorting (shared)
    def _items(self, specs):
        idx = self.order if self.scope_full() else self.model.view
        return sorting.build_items(self.records, idx, specs, KIND)

    def _busy(self, on):
        for b in (self.btn_sort, self.btn_bench, self.ms_apply):
            b.setEnabled(not on)
        self.btn_cancel.setVisible(on)
        self.ms_cancel.setVisible(on)

    def start_sort(self, specs, algo):
        if self.task and self.task.isRunning():
            return
        if not self.records:
            return info(self, "There are no laptops yet. Scrape or import some first.")
        items = self._items(specs)
        if len(items) > 6000 and algo in sorting.QUADRATIC:
            ans = QMessageBox.question(self, "Laptop Ledger", f"{algo} is O(n²) and {len(items):,} rows can take minutes. Continue? "
                                       "You can cancel at any time.")
            if ans != QMessageBox.Yes:
                return
        full = self.scope_full()
        self.task = Task(lambda t: sorting.run_sort(algo, items, t.stop_flag), self)
        self.task.done.connect(lambda res: self._sort_done(res, specs, algo, full))
        self.task.failed.connect(self._sort_failed)
        self._busy(True)
        self.tiles["ms"].setText("…")
        self.task.start()

    def _sort_failed(self, msg):
        self._busy(False)
        for t in self.tiles.values():
            t.setText("-")
        if msg != "Cancelled":
            warn(self, msg)
        else:
            self.algo_info.setText("Sort cancelled.")

    def _sort_done(self, res, specs, algo, full):
        items, st, ms = res
        idx = [i for _, i in items]
        if full:
            self.order = idx
            view = idx if self.fset is None else [i for i in idx if i in self.fset]
        else:
            view = idx
        mark = None
        if len(specs) == 1:
            mark = (KEYS.index(specs[0][0]), specs[0][1])
            self.sort_col, self.sort_desc = specs[0]
        else:
            self.sort_col = None
        self.model.set_view(view, mark)
        self._busy(False)
        self.tiles["ms"].setText(f"{ms:,.2f}")
        self.tiles["cmp"].setText(f"{st.comparisons:,}")
        self.tiles["swp"].setText(f"{st.swaps:,}")
        self.tiles["n"].setText(f"{len(items):,}")
        names = " then ".join(f"{LABEL[c]} {'desc' if d else 'asc'}" for c, d in specs)
        self.algo_info.setText(f"{algo}: {names}. {sorting.describe(algo)}")
        self.table.scrollToTop()
        self._refresh_counts()
        self.go(1)

    def open_benchmark(self):
        if not self.records:
            return info(self, "There are no laptops yet. Scrape or import some first.")
        key = self.sort_col_box.currentData()
        items = self._items([(key, self.sort_order.currentIndex() == 1)])
        scope = "full dataset" if self.scope_full() else "filtered results"
        BenchmarkDialog(self, items, LABEL[key], scope).exec_()

    # ---------------------------------------------------------------- filters page
    def _build_filters(self):
        w, lay = page("Search & filters", "Build a filter from one or more conditions. Combine them with AND / OR, "
                      "and tick NOT to invert a condition. Conditions are evaluated from top to bottom.")
        c, cl = card()
        cl.addWidget(label("Conditions", "section"))
        self.cond_box = QVBoxLayout()
        self.cond_box.setSpacing(8)
        cl.addLayout(self.cond_box)
        self.conds = []
        self.add_condition()
        add, apply, clear = ghost("Add condition"), button("Apply filter"), ghost("Clear filter")
        add.clicked.connect(self.add_condition)
        apply.clicked.connect(self.apply_filters)
        clear.clicked.connect(self.clear_filters)
        cl.addLayout(row(add, 1, clear, apply))
        lay.addWidget(c)
        c2, l2 = card()
        l2.addWidget(label("Search report", "section"))
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setPlaceholderText("Per-condition matches, comparisons and time appear here after you apply a filter.")
        l2.addWidget(self.report, 1)
        lay.addWidget(c2, 1)
        return w

    def add_condition(self):
        r = ConditionRow(first=not self.conds)
        r.removed.connect(self.remove_condition)
        self.conds.append(r)
        self.cond_box.addWidget(r)

    def remove_condition(self, r):
        self.conds.remove(r)
        self.cond_box.removeWidget(r)
        r.deleteLater()

    def apply_filters(self):
        if not self.records:
            return info(self, "There are no laptops yet. Scrape or import some first.")
        specs = [r.spec() for r in self.conds]
        results, lines, words, total_ms = [], [], [], 0.0
        for n, s in enumerate(specs, 1):
            if not s["v1"].strip() or (s["op"] == "between" and not s["v2"].strip()):
                return warn(self, f"Condition {n} needs a value.")
            try:
                res, cmps, ms = searching.search(self.records, self.cache, s["col"], s["kind"], s["op"], s["v1"], s["v2"], s["algo"])
            except ValueError:
                return warn(self, f"Condition {n}: “{LABEL[s['col']]}” is a number column, so enter a number.")
            results.append(res)
            total_ms += ms
            desc = f"{LABEL[s['col']]} {s['op']} {s['v1'].strip()}" + (f" and {s['v2'].strip()}" if s["op"] == "between" else "")
            desc = ("NOT " if s["negate"] else "") + desc
            words.append((s["connector"] + " " if n > 1 else "") + desc)
            lines.append(f"{n}. {desc}  [{s['algo']}]  {len(res):,} matches, {cmps:,} comparisons, {ms:,.2f} ms")
        self.fset = searching.combine(len(self.records), specs, results)
        self.filter_text = "  ".join(words)
        self.model.set_view([i for i in self.order if i in self.fset])
        lines.append(f"\nCombined result: {len(self.fset):,} of {len(self.records):,} laptops ({total_ms:,.2f} ms of searching).")
        self.report.setPlainText("\n".join(lines))
        self.banner_text.setText(f"Filter: {self.filter_text}")
        self.banner.show()
        self._refresh_counts()
        self.go(1)

    def clear_filters(self):
        self.fset = None
        self.banner.hide()
        self.model.set_view(list(self.order))
        self.report.clear()
        self._refresh_counts()

    # ---------------------------------------------------------------- multi-level sort page
    def _build_multisort(self):
        w, lay = page("Multi-level sort", "Sort by several columns at once: rows are ordered by the first level, "
                      "ties are broken by the second, then the third.")
        c, cl = card()
        cl.addWidget(label("Sort levels", "section"))
        self.levels = []
        for n in range(3):
            col = QComboBox()
            if n:
                col.addItem("(none)", None)
            for key in KEYS:
                col.addItem(LABEL[key], key)
            order = QComboBox()
            order.addItems(["Ascending", "Descending"])
            col.setMinimumWidth(180)
            self.levels.append((col, order))
            cl.addLayout(row(label(["Sort by", "Then by", "Then by"][n]), col, order, 1))
        self.levels[0][0].setCurrentIndex(KEYS.index("brand"))
        self.levels[1][0].setCurrentIndex(1 + KEYS.index("price"))
        self.ms_algo = self._algo_combo()
        self.ms_algo.setCurrentText("Merge Sort")
        self.ms_info = label(sorting.describe("Merge Sort"), "hint")
        self.ms_algo.currentTextChanged.connect(lambda n: self.ms_info.setText(sorting.describe(n)))
        self.ms_apply, self.ms_cancel = button("Apply multi-level sort"), ghost("Cancel")
        self.ms_cancel.hide()
        self.ms_apply.clicked.connect(self.apply_multisort)
        self.ms_cancel.clicked.connect(lambda: self.task and self.task.stop_flag.set())
        cl.addLayout(row(label("Algorithm"), self.ms_algo, self.ms_info, 1))
        cl.addLayout(row(self._scope_widget(), 1, self.ms_cancel, self.ms_apply))
        lay.addWidget(c)
        lay.addStretch(1)
        return w

    def apply_multisort(self):
        specs = [(col.currentData(), order.currentIndex() == 1) for col, order in self.levels if col.currentData()]
        if len({c for c, _ in specs}) != len(specs):
            return warn(self, "Each level should use a different column.")
        self.start_sort(specs, self.ms_algo.currentText())

    # ---------------------------------------------------------------- shutdown
    def closeEvent(self, e):
        for t in (self.worker, self.task):
            if t and t.isRunning():
                if t is self.worker:
                    t.stop()
                else:
                    t.stop_flag.set()
                t.wait(3000)
        if self.records:
            self._autosave()
        super().closeEvent(e)
