"""Launch with `uv run ui.py`. UI runs independently of the recognition models."""

import sys
from dataclasses import replace
from pathlib import Path
from string import Template

from PySide6.QtCore import (
    QIODevice,
    QObject,
    QSaveFile,
    QSignalBlocker,
    QSize,
    Qt,
    QThread,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDesktopServices,
    QIcon,
    QImage,
    QImageReader,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ui_model import PhotoPair, load_pairs

APP_ICON_PATH = Path(__file__).resolve().parent / "assets" / "app-icon.ico"

THEMES = {
    "dark": {
        "background": "#0E0E0E", "text": "#FFFFFF", "surface": "#181818",
        "border": "#303030", "eyebrow": "#A3A3A3", "muted": "#A3A3A3",
        "filename": "#A3A3A3", "photo": "#0E0E0E", "button_border": "#404040",
        "hover": "#163323", "hover_border": "#22C55E", "pressed": "#1b4930",
        "focus": "#22C55E", "disabled": "#262626", "disabled_text": "#A3A3A3",
        "disabled_border": "#303030", "input_disabled": "#222222",
        "item_hover": "#242424", "scroll_track": "#181818", "scroll_handle": "#404040",
        "scroll_hover": "#606060", "progress": "#262626", "accent": "#22C55E",
        "primary": "#22C55E", "primary_text": "#0E0E0E", "primary_border": "#22C55E",
        "primary_hover": "#16a34a",
    },
    "light": {
        "background": "#f4f5f1", "text": "#243128", "surface": "#ffffff",
        "border": "#dfe5de", "eyebrow": "#65725f", "muted": "#68736b",
        "filename": "#53634f", "photo": "#e9ece5", "button_border": "#d4ddd1",
        "hover": "#e9efdf", "hover_border": "#a6ba99", "pressed": "#dce8d0",
        "focus": "#719553", "disabled": "#e8eae4", "disabled_text": "#8a9388",
        "disabled_border": "#e0e4dc", "input_disabled": "#ecefe8",
        "item_hover": "#f2f5ee", "scroll_track": "#edf0e9", "scroll_handle": "#bdc8b6",
        "scroll_hover": "#96aa89", "progress": "#e1e7da", "accent": "#7a9d54",
        "primary": "#bce57a", "primary_text": "#203418", "primary_border": "#aed16f",
        "primary_hover": "#add666",
    },
}

STYLE = Template("""
QWidget { background: $background; color: $text; font-family: 'Segoe UI', sans-serif; font-size: 14px; }
QMainWindow { background: $background; }
QFrame#header, QFrame#sidebar, QFrame#preview { background: $surface; }
QFrame#header { border-bottom: 1px solid $border; }
QFrame#sidebar { border-right: 1px solid $border; }
QFrame#preview { border: 1px solid $border; border-radius: 12px; }
QLabel { background: transparent; }
QLabel#brand { font-size: 18px; font-weight: 600; }
QLabel#title { font-size: 29px; font-weight: 600; }
QLabel#eyebrow { font-size: 11px; font-weight: 600; color: $eyebrow; }
QLabel#muted { color: $muted; font-size: 12px; }
QLabel#filename { color: $filename; font-family: monospace; font-size: 12px; }
QLabel#photo { background: $photo; border-radius: 8px; color: $muted; padding: 8px; }
QPushButton { background: $surface; border: 1px solid $button_border; border-radius: 7px; padding: 10px 15px; }
QPushButton:hover { background: $hover; border-color: $hover_border; }
QPushButton:pressed { background: $pressed; }
QPushButton:focus, QLineEdit:focus, QListWidget:focus { border: 2px solid $focus; }
QPushButton#themeToggle { font-size: 22px; padding: 0px; }
QPushButton#primary { background: $primary; color: $primary_text; border-color: $primary_border; font-weight: 600; }
QPushButton#primary:hover { background: $primary_hover; }
QPushButton#primary:disabled { background: $disabled; color: $disabled_text; border-color: $disabled_border; }
QPushButton#exportButton:enabled { background: #22C55E; color: #0E0E0E; border-color: #22C55E; font-weight: 600; }
QPushButton#exportButton:enabled:hover { background: #4ade80; }
QPushButton#exportButton:enabled:pressed { background: #16a34a; }
QPushButton:disabled { background: $disabled; color: $disabled_text; border-color: $disabled_border; }
QLineEdit { background: $surface; border: 1px solid $button_border; border-radius: 7px; padding: 10px; selection-background-color: $hover; selection-color: $text; }
QLineEdit:disabled { background: $input_disabled; color: $disabled_text; }
QListWidget { background: $surface; border: none; padding: 4px; outline: none; }
QListWidget::item { padding: 15px 12px; margin: 3px; border-radius: 8px; }
QListWidget::item:selected { background: $hover; color: $text; }
QListWidget::item:hover:!selected { background: $item_hover; }
QScrollArea { border: none; }
QScrollBar:vertical { background: $scroll_track; width: 10px; margin: 2px; border: none; border-radius: 3px; }
QScrollBar:horizontal { background: $scroll_track; height: 10px; margin: 2px; border: none; border-radius: 3px; }
QScrollBar::handle { background: $scroll_handle; border-radius: 3px; }
QScrollBar::handle:vertical { min-height: 32px; }
QScrollBar::handle:horizontal { min-width: 32px; }
QScrollBar::handle:hover { background: $scroll_hover; }
QScrollBar::handle:pressed { background: $accent; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0px; height: 0px; border: none; background: transparent; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QProgressBar { border: none; background: $progress; border-radius: 3px; max-height: 6px; }
QProgressBar::chunk { background: $accent; border-radius: 3px; }
QSplitter::handle { background: $border; width: 1px; }
QToolTip { background: $surface; color: $text; border: 1px solid $border; padding: 6px; }
""")


def label(text: str, kind: str = "", wrap: bool = False) -> QLabel:
    widget = QLabel(text)
    widget.setObjectName(kind)
    widget.setWordWrap(wrap)
    return widget


def button(text: str, callback, primary: bool = False) -> QPushButton:
    widget = QPushButton(text)
    if primary:
        widget.setObjectName("primary")
    widget.clicked.connect(callback)
    return widget


def read_image(path: Path, preview: bool = False) -> QImage:
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    if preview:
        size = reader.size()
        if size.isValid():
            reader.setScaledSize(size.scaled(1000, 1000, Qt.AspectRatioMode.KeepAspectRatio))
    image = reader.read()
    if image.isNull():
        raise ValueError(f"Cannot open {path.name}: {reader.errorString()}")
    return image


def recognize_name(path: Path) -> str:
    # Load the models only in the background worker, not during UI startup.
    from recognize_image import hash_recognize

    result = hash_recognize(path, None)
    if not isinstance(result, str) or not result.strip():
        raise ValueError("No card name was recognized")
    name = result.strip()
    if name.lower().endswith(".png"):
        name = name[:-4].strip()
    if not name or PhotoPair(0, path, name=name).filename == "unknown.png":
        raise ValueError("No usable card name was recognized")
    return name


def initialize_recognition(report):
    report("Loading recognition models…", 0)
    # Importing this module loads the detection models as well as their libraries.
    import recognize_image  # noqa: F401

    report("Loading card hashes…", 0)
    from recognition_backend import get_recognizer

    get_recognizer()


class RecognitionWorker(QObject):
    progress = Signal(int, object)
    stage = Signal(str, int)
    completed = Signal()

    def __init__(self, pairs: list[PhotoPair]):
        super().__init__()
        self.pairs = pairs

    def run(self):
        initialization_error = ""
        try:
            initialize_recognition(self.stage.emit)
        except Exception as exc:
            initialization_error = str(exc) or type(exc).__name__
        self.stage.emit("Recognizing card names…", len(self.pairs))
        for count, pair in enumerate(self.pairs, 1):
            pair = replace(pair, name="", confirmed=False, exported=False,
                           error="", recognition_failed=False, recognition_error="")
            errors = []
            for path in (pair.front, pair.back):
                if path:
                    try:
                        read_image(path, preview=True)
                    except Exception as exc:
                        errors.append(str(exc))
            pair.error = "\n".join(errors)
            try:
                if initialization_error:
                    raise RuntimeError(initialization_error)
                pair.name = recognize_name(pair.front)
            except Exception as exc:
                pair.recognition_failed = True
                pair.recognition_error = str(exc)
            pair.confirmed = bool(pair.name and pair.back and not pair.error and not pair.skipped)
            self.progress.emit(count, pair)
        self.completed.emit()


class PhotoPreview(QWidget):
    def __init__(self, side: str):
        super().__init__()
        self.image = QImage()
        self.side = side
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.photo = label("No photo", "photo")
        self.photo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.photo.setMinimumSize(160, 235)
        self.photo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.caption = label(side, "muted", True)
        self.caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.photo, 1)
        layout.addWidget(self.caption)

    def set_path(self, path: Path | None) -> str:
        self.image = QImage()
        self.photo.clear()
        self.caption.setText(f"{self.side} · {path.name}" if path else self.side)
        self.caption.setToolTip(str(path) if path else "")
        if path is None:
            self.photo.setText("Missing photo")
            return ""
        try:
            self.image = read_image(path, preview=True)
        except ValueError as exc:
            self.photo.setText("Image unavailable")
            return str(exc)
        self.fit()
        return ""

    def fit(self):
        if not self.image.isNull():
            self.photo.setPixmap(
                QPixmap.fromImage(self.image).scaled(
                    self.photo.size() - QSize(18, 18),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit()


class ExportWorker(QObject):
    progress = Signal(int, str)
    completed = Signal(object, object)

    def __init__(self, pairs: list[PhotoPair], destination: Path,
                 delete_after_export: bool = False, input_folder: Path | None = None,
                 preserved_sources: tuple[Path, ...] = ()):
        super().__init__()
        self.pairs = pairs
        self.destination = destination
        self.written_pair_indices: set[int] = set()
        self.delete_after_export = delete_after_export
        self.input_folder = input_folder
        self.cleanup_errors: list[str] = []
        self.preserved_sources = preserved_sources

    def run(self):
        written, errors = [], []
        for index, pair in enumerate(self.pairs, 1):
            path = self.destination / pair.filename
            claimed = False
            try:
                # Reserve without overwriting any existing files, even after preflight.
                with path.open("xb"):
                    claimed = True
                front, back = read_image(pair.front), read_image(pair.back)
                merged = QImage(
                    front.width() + back.width(),
                    max(front.height(), back.height()),
                    QImage.Format.Format_RGB32,
                )
                if merged.isNull():
                    raise ValueError("Not enough memory to merge these photographs")
                merged.fill(Qt.GlobalColor.white)
                painter = QPainter(merged)
                painter.drawImage(0, 0, front)
                painter.drawImage(front.width(), 0, back)
                painter.end()
                output = QSaveFile(str(path))
                if not output.open(QIODevice.OpenModeFlag.WriteOnly):
                    raise OSError(output.errorString())
                if not merged.save(output, "PNG"):
                    output.cancelWriting()
                    raise OSError("Could not encode PNG")
                if not output.commit():
                    raise OSError(output.errorString())
                written.append(str(path))
                self.written_pair_indices.add(pair.index)
            except Exception as exc:
                error = f"{pair.filename}: {exc}"
                if claimed:
                    try:
                        path.unlink(missing_ok=True)
                    except OSError as cleanup_error:
                        error += f"\nCould not remove incomplete file {path.name}: {cleanup_error}"
                errors.append(error)
            self.progress.emit(index, pair.filename)
        if self.delete_after_export and self.input_folder:
            # Wait until all exports finish: a photo can be shared by multiple pairs.
            protected = {
                source.resolve()
                for pair in self.pairs if pair.index not in self.written_pair_indices
                for source in (pair.front, pair.back) if source
            }
            protected.update(source.resolve() for source in self.preserved_sources)
            sources = {
                source for pair in self.pairs if pair.index in self.written_pair_indices
                for source in (pair.front, pair.back) if source
            }
            for source in sources:
                if (source.parent.resolve() != self.input_folder.resolve()
                        or source.resolve() in protected):
                    continue
                try:
                    source.unlink(missing_ok=True)
                except OSError as exc:
                    self.cleanup_errors.append(f"Could not delete {source.name}: {exc}")
        self.completed.emit(written, errors)


class CardMergerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.pairs: list[PhotoPair] = []
        self.input_folder: Path | None = None
        self.output_folder: Path | None = None
        self.thread: QThread | None = None
        self.worker: ExportWorker | RecognitionWorker | None = None
        self.setWindowTitle("Card Merger")
        self.setWindowIcon(QIcon(str(APP_ICON_PATH)))
        self.resize(1120, 800)
        self.setMinimumSize(780, 640)
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QFrame()
        header.setObjectName("header")
        row = QHBoxLayout(header)
        row.setContentsMargins(24, 16, 24, 16)
        row.addWidget(label("▥  Card Merger", "brand"))
        row.addStretch()
        row.addWidget(label("LOCAL WORKSPACE", "eyebrow"))
        self.theme_button = button("", self.toggle_theme)
        self.theme_button.setObjectName("themeToggle")
        self.theme_button.setFixedSize(42, 42)
        row.addWidget(self.theme_button)
        self.set_theme("dark")
        self.import_button = button("Choose photo folder…", self.choose_input)
        row.addWidget(self.import_button)
        outer.addWidget(header)

        self.splitter = QSplitter()
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(12, 22, 12, 16)
        side.addWidget(label("PHOTO PAIRS", "eyebrow"))
        self.count = label("No photos loaded", "muted")
        side.addWidget(self.count)
        self.queue = QListWidget()
        self.queue.setAccessibleName("Photo pair queue")
        self.queue.currentRowChanged.connect(self.select_pair)
        side.addWidget(self.queue, 1)
        side.addWidget(
            label("Sorted by filename number.\nEvery two photos form a pair.", "muted", True)
        )
        self.splitter.addWidget(sidebar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        workspace = QWidget()
        work = QVBoxLayout(workspace)
        work.setContentsMargins(28, 24, 28, 24)
        work.setSpacing(14)
        work.addWidget(label("REVIEW & PREPARE", "eyebrow"))
        work.addWidget(label("One card. Both sides.", "title"))
        work.addWidget(label("Names are recognized automatically. You can override any card name below.", "muted"))
        self.preview = QFrame()
        self.preview.setObjectName("preview")
        preview_layout = QVBoxLayout(self.preview)
        preview_layout.setContentsMargins(18, 16, 18, 16)
        preview_header = QHBoxLayout()
        self.pair_title = label("Choose a folder to get started", "brand")
        preview_header.addWidget(self.pair_title, 1)
        self.swap_button = button("⇄  Swap sides", self.swap_sides)
        preview_header.addWidget(self.swap_button)
        preview_layout.addLayout(preview_header)
        photos = QHBoxLayout()
        photos.setSpacing(16)
        self.front = PhotoPreview("Front")
        self.back = PhotoPreview("Back")
        photos.addWidget(self.front)
        photos.addWidget(self.back)
        preview_layout.addLayout(photos, 1)
        preview_layout.addWidget(label("Output: original photos, side by side · PNG", "muted"))
        work.addWidget(self.preview, 1)

        # Keep naming and review actions visible even on smaller desktop windows.
        editor = QWidget()
        work = QVBoxLayout(editor)
        work.setContentsMargins(28, 10, 28, 14)
        work.setSpacing(10)
        self.notice = label(
            "Photos stay on your computer. Check the deletion option before exporting.", "muted", True
        )
        self.notice.setAccessibleName("Pair status")
        work.addWidget(self.notice)
        field = QVBoxLayout()
        self.recognized_name = label("", "brand", True)
        work.addWidget(self.recognized_name)
        self.manual_naming = QWidget()
        name_row = QHBoxLayout(self.manual_naming)
        name_row.setContentsMargins(0, 0, 0, 0)
        name_label = label("Card name — edit to override recognition")
        self.name = QLineEdit()
        self.name.setPlaceholderText("Enter the card name")
        name_label.setBuddy(self.name)
        self.name.textEdited.connect(self.edit_name)
        self.name.returnPressed.connect(self.confirm_pair)
        field.addWidget(name_label)
        field.addWidget(self.name)
        name_row.addLayout(field, 1)
        self.confirm_button = button("Confirm pair", self.confirm_pair, True)
        name_row.addWidget(self.confirm_button, 0, Qt.AlignmentFlag.AlignBottom)
        work.addWidget(self.manual_naming)
        self.filename = label("", "filename", True)
        work.addWidget(self.filename)
        pair_actions = QHBoxLayout()
        self.replace_button = button("Replace back photo…", self.replace_back)
        self.skip_button = button("Skip pair", self.skip_pair)
        pair_actions.addWidget(self.replace_button)
        pair_actions.addWidget(self.skip_button)
        pair_actions.addStretch()
        work.addLayout(pair_actions)
        scroll.setWidget(workspace)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addWidget(scroll, 1)
        right_layout.addWidget(editor)
        self.splitter.addWidget(right)
        self.splitter.setSizes([235, 885])
        self.splitter.setStretchFactor(1, 1)
        outer.addWidget(self.splitter, 1)

        footer = QFrame()
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(24, 12, 24, 18)
        output_row = QHBoxLayout()
        self.output_label = label("Choose where to save merged cards", "muted", True)
        output_row.addWidget(self.output_label, 1)
        self.output_button = button("Output folder…", self.choose_output)
        output_row.addWidget(self.output_button)
        footer_layout.addLayout(output_row)
        self.delete_after_export = QCheckBox("Delete input photos after successful export")
        self.delete_after_export.setChecked(True)
        self.delete_after_export.setToolTip(
            "Permanently delete successfully exported source photos from the input folder. "
            "Uncheck to keep originals. Photos outside the input folder are kept."
        )
        footer_layout.addWidget(self.delete_after_export)
        bottom = QHBoxLayout()
        self.summary = label("Import photos to begin", "muted", True)
        bottom.addWidget(self.summary, 1)
        self.export_button = button("Export confirmed pairs", self.export_pairs, True)
        self.export_button.setObjectName("exportButton")
        bottom.addWidget(self.export_button)
        footer_layout.addLayout(bottom)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setAccessibleName("Export progress")
        self.progress.hide()
        footer_layout.addWidget(self.progress)
        outer.addWidget(footer)
        open_action = QAction("Open photo folder…", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.choose_input)
        self.addAction(open_action)
        self.refresh()

    def set_theme(self, theme: str):
        self.setStyleSheet(STYLE.substitute(THEMES[theme]))
        self.theme = theme
        next_theme = "light" if theme == "dark" else "dark"
        self.theme_button.setText("☀" if theme == "dark" else "☾")
        self.theme_button.setToolTip(f"Current theme: {theme}. Switch to {next_theme} mode.")
        self.theme_button.setAccessibleName(f"Switch to {next_theme} mode")

    def toggle_theme(self):
        self.set_theme("light" if self.theme == "dark" else "dark")

    @property
    def current_pair(self) -> PhotoPair | None:
        row = self.queue.currentRow()
        return self.pairs[row] if 0 <= row < len(self.pairs) else None

    def choose_input(self):
        if self.thread:
            return
        folder = QFileDialog.getExistingDirectory(self, "Choose photo folder")
        if folder:
            self.load_folder(Path(folder))

    def load_folder(self, folder: Path):
        if self.thread:
            return
        if self.pairs:
            answer = QMessageBox.question(
                self,
                "Replace current batch?",
                "Loading another folder replaces the current review. Continue?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            pairs = load_pairs(folder)
        except OSError as exc:
            QMessageBox.warning(self, "Cannot read folder", str(exc))
            return
        self.pairs, self.input_folder = pairs, folder
        with QSignalBlocker(self.queue):
            self.queue.clear()
            for _ in pairs:
                self.queue.addItem(QListWidgetItem())
        self.count.setText(f"{len(pairs)} pairs · {sum(1 + bool(p.back) for p in pairs)} photos")
        self.count.setToolTip(str(folder))
        self.refresh()
        self.queue.setCurrentRow(0 if pairs else -1)
        if not pairs:
            self.select_pair(-1)
            self.notice.setText(
                "No supported photos found. Choose a folder with JPG, PNG, WebP, BMP or TIFF files."
            )
        else:
            self.start_recognition(pairs)

    def start_recognition(self, pairs: list[PhotoPair]):
        self.set_busy(True)
        self.progress.setAccessibleName("Recognition progress")
        self.recognition_stage("Loading recognition models…", 0)
        self.thread = QThread(self)
        self.worker = RecognitionWorker([replace(pair) for pair in pairs])
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.recognition_progress)
        self.worker.stage.connect(self.recognition_stage)
        self.worker.completed.connect(self.thread.quit)
        self.worker.completed.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.recognition_finished)
        self.thread.start()

    def recognition_stage(self, message: str, total: int):
        # A 0..0 range is Qt's animated busy bar, not a misleading percentage.
        self.progress.setRange(0, total)
        self.progress.setValue(0)
        self.summary.setText(message)
        self.notice.setText(message)

    def recognition_progress(self, count: int, pair: PhotoPair):
        self.pairs[pair.index - 1] = pair
        self.progress.setValue(count)
        self.select_pair(self.queue.currentRow())
        self.summary.setText(f"Recognizing card names… {count}/{self.progress.maximum()}")

    def recognition_finished(self):
        self.thread = self.worker = None
        self.set_busy(False)
        self.refresh()

    def choose_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if folder:
            self.output_folder = Path(folder)
            self.output_label.setText(f"Save to: {folder}")
            self.refresh()

    def select_pair(self, _row: int):
        pair = self.current_pair
        self.name.setText(pair.name if pair else "")
        self.pair_title.setText(
            f"Pair {pair.index:03d}" if pair else "Choose a folder to get started"
        )
        errors = [
            self.front.set_path(pair.front if pair else None),
            self.back.set_path(pair.back if pair else None),
        ]
        if pair and not pair.exported:
            pair.error = "\n".join(filter(None, errors))
            if pair.error:
                pair.confirmed = False
        self.refresh()

    def refresh(self):
        pair = self.current_pair
        for row, item_pair in enumerate(self.pairs):
            self.queue.item(row).setText(
                f"{item_pair.name or f'Pair {item_pair.index:03d}'}\n{item_pair.status}"
            )
        self.name.setEnabled(bool(pair) and not pair.skipped)
        self.manual_naming.setVisible(bool(pair))
        self.recognized_name.setVisible(bool(pair and not pair.recognition_failed))
        self.recognized_name.setText(f"Card name: {pair.name}" if pair and pair.name else "Recognizing card name…")
        self.name.setToolTip(pair.recognition_error if pair else "")
        self.swap_button.setEnabled(bool(pair and pair.back))
        self.replace_button.setEnabled(bool(pair))
        self.skip_button.setEnabled(bool(pair))
        self.skip_button.setText("Restore pair" if pair and pair.skipped else "Skip pair")
        self.confirm_button.setEnabled(
            bool(
                pair
                and pair.back
                and pair.name.strip()
                and not pair.error
                and not pair.skipped
                and not pair.confirmed
            )
        )
        self.confirm_button.setText("✓ Confirmed" if pair and pair.confirmed else "Confirm pair")
        self.filename.setText(pair.filename if pair else "")
        if pair:
            self.notice.setText(
                pair.error
                or (
                    "This pair will be left out of the export."
                    if pair.skipped
                    else "Missing back photo. Replace it or skip this pair."
                    if not pair.back
                    else "Pair exported."
                    if pair.exported
                    else "Pair confirmed and ready to export."
                    if pair.confirmed
                    else "Recognition failed. Enter a card name and confirm this pair."
                    if pair.recognition_failed
                    else "Confirm this pair to use the updated card name."
                    if pair.name
                    else "Recognizing card name…"
                )
            )
        confirmed = sum(p.confirmed and not p.skipped for p in self.pairs)
        pending = sum(p.confirmed and not p.skipped and not p.exported for p in self.pairs)
        exported = sum(p.exported for p in self.pairs)
        skipped = sum(p.skipped for p in self.pairs)
        self.summary.setText(
            f"{confirmed} of {len(self.pairs)} pairs confirmed · {exported} exported · {skipped} skipped"
            if self.pairs
            else "Import photos to begin"
        )
        self.export_button.setText(
            f"Export {pending} confirmed {'pair' if pending == 1 else 'pairs'}"
        )
        self.export_button.setEnabled(bool(pending and self.output_folder and not self.thread))

    def edit_name(self, text: str):
        if (pair := self.current_pair) and not pair.skipped and not self.thread:
            pair.name, pair.confirmed = text, False
            pair.exported = False
            self.refresh()

    def confirm_pair(self):
        pair = self.current_pair
        if pair and pair.back and pair.name.strip() and not pair.error and not pair.skipped:
            pair.confirmed = True
            self.refresh()

    def swap_sides(self):
        if (pair := self.current_pair) and pair.back:
            pair.front, pair.back = pair.back, pair.front
            pair.confirmed = False
            pair.exported = False
            self.select_pair(self.queue.currentRow())
            self.start_recognition([pair])

    def replace_back(self):
        pair = self.current_pair
        if pair is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose back photo",
            str(self.input_folder or ""),
            "Photos (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff)",
        )
        if path:
            pair.back, pair.confirmed = Path(path), False
            pair.exported = False
            self.select_pair(self.queue.currentRow())
            pair.confirmed = bool(pair.name.strip() and not pair.error and not pair.skipped)
            self.refresh()

    def skip_pair(self):
        if pair := self.current_pair:
            pair.skipped = not pair.skipped
            pair.confirmed = bool(not pair.skipped and pair.name.strip() and pair.back and not pair.error)
            self.refresh()

    def export_pairs(self):
        pairs = [replace(p) for p in self.pairs if p.confirmed and not p.skipped and not p.exported]
        if not pairs or not self.output_folder or self.thread:
            return
        if self.input_folder and self.output_folder.resolve() == self.input_folder.resolve():
            QMessageBox.warning(
                self,
                "Choose a different output folder",
                "Save merged cards in a separate folder so they are not imported as source photos next time.",
            )
            return
        collisions = [p.filename for p in pairs if (self.output_folder / p.filename).exists()]
        if collisions:
            QMessageBox.warning(
                self,
                "Files already exist",
                "Choose another output folder. Existing files will not be overwritten.\n\n"
                + "\n".join(collisions[:10]),
            )
            return
        self.set_busy(True)
        self.progress.setAccessibleName("Export progress")
        self.progress.setRange(0, len(pairs))
        self.progress.setValue(0)
        self.thread = QThread(self)
        self.worker = ExportWorker(
            pairs, self.output_folder, self.delete_after_export.isChecked(), self.input_folder,
            tuple(source for pair in self.pairs if not pair.confirmed or pair.skipped
                  for source in (pair.front, pair.back) if source),
        )
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.export_progress)
        self.worker.completed.connect(self.export_complete)
        self.worker.completed.connect(self.thread.quit)
        self.worker.completed.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.export_finished)
        self.thread.start()

    def set_busy(self, busy: bool):
        self.splitter.setEnabled(not busy)
        self.import_button.setEnabled(not busy)
        self.output_button.setEnabled(not busy)
        self.export_button.setEnabled(not busy)
        self.delete_after_export.setEnabled(not busy)
        self.progress.setVisible(busy)

    def export_progress(self, count: int, filename: str):
        self.progress.setValue(count)
        self.summary.setText(f"Exporting {filename}…")

    def export_complete(self, written: list[str], errors: list[str]):
        self.last_export = (written, errors)
        self.last_cleanup_errors = self.worker.cleanup_errors
        saved = {Path(path) for path in written}
        for pair in self.pairs:
            if self.output_folder / pair.filename in saved:
                pair.exported = True

    def export_finished(self):
        self.thread = self.worker = None
        self.set_busy(False)
        self.refresh()
        written, errors = self.last_export
        self.summary.setText(f"Export complete · {len(written)} saved · {len(errors)} failed")
        message = QMessageBox(self)
        message.setWindowTitle("Export complete")
        message.setText(f"{len(written)} merged PNG files saved.\n{len(errors)} pairs failed.")
        message.setInformativeText(
            "Successfully exported input photos were deleted. Photos outside the input folder were kept."
            if self.delete_after_export.isChecked()
            else "Your original photos have been preserved."
        )
        if self.last_cleanup_errors:
            message.setInformativeText("Export saved, but some input photos could not be deleted.")
        issues = errors + self.last_cleanup_errors
        message.setIcon(QMessageBox.Icon.Warning if issues else QMessageBox.Icon.Information)
        if issues:
            message.setDetailedText("\n".join(issues))
        show_folder = message.addButton("Open output folder", QMessageBox.ButtonRole.ActionRole)
        message.addButton(QMessageBox.StandardButton.Close)
        message.exec()
        if message.clickedButton() == show_folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output_folder)))

    def closeEvent(self, event: QCloseEvent):
        if self.thread:
            QMessageBox.information(
                self, "Processing photos", "Please wait for processing to finish before closing."
            )
            event.ignore()
        else:
            event.accept()


def main():
    if sys.platform == "win32":
        import ctypes

        # Keep the taskbar icon separate from the Python interpreter's icon.
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PokemonCardMerger.Desktop")
    app = QApplication(sys.argv)
    app.setApplicationName("Card Merger")
    app.setWindowIcon(QIcon(str(APP_ICON_PATH)))
    window = CardMergerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
