# /// script
# requires-python = ">=3.12"
# dependencies = ["PySide6>=6.8,<7"]
# ///
"""Launch with `uv run ui.py`. UI runs independently of the recognition models."""

import sys
from dataclasses import replace
from pathlib import Path

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
    QImage,
    QImageReader,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
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

STYLE = """
QWidget { background: #f4f5f1; color: #243128; font-family: 'Segoe UI', sans-serif; font-size: 14px; }
QMainWindow { background: #f4f5f1; }
QFrame#header, QFrame#sidebar, QFrame#preview { background: #ffffff; }
QFrame#header { border-bottom: 1px solid #dfe5de; }
QFrame#sidebar { border-right: 1px solid #dfe5de; }
QFrame#preview { border: 1px solid #dfe5de; border-radius: 12px; }
QLabel { background: transparent; }
QLabel#brand { font-size: 18px; font-weight: 600; }
QLabel#title { font-size: 29px; font-weight: 600; }
QLabel#eyebrow { font-size: 11px; font-weight: 600; color: #65725f; }
QLabel#muted { color: #68736b; font-size: 12px; }
QLabel#filename { color: #53634f; font-family: monospace; font-size: 12px; }
QLabel#photo { background: #e9ece5; border-radius: 8px; color: #68736b; padding: 8px; }
QPushButton { background: #ffffff; border: 1px solid #d4ddd1; border-radius: 7px; padding: 10px 15px; }
QPushButton:hover { background: #e9efdf; border-color: #a6ba99; }
QPushButton:pressed { background: #dce8d0; }
QPushButton:focus, QLineEdit:focus, QListWidget:focus { border: 2px solid #719553; }
QPushButton#primary { background: #bce57a; color: #203418; border-color: #aed16f; font-weight: 600; }
QPushButton#primary:hover { background: #add666; }
QPushButton:disabled { background: #e8eae4; color: #8a9388; border-color: #e0e4dc; }
QLineEdit { background: #ffffff; border: 1px solid #d4ddd1; border-radius: 7px; padding: 10px; }
QLineEdit:disabled { background: #ecefe8; color: #8a9388; }
QListWidget { background: #ffffff; border: none; padding: 4px; outline: none; }
QListWidget::item { padding: 15px 12px; margin: 3px; border-radius: 8px; }
QListWidget::item:selected { background: #e9efdf; color: #243128; }
QListWidget::item:hover:!selected { background: #f2f5ee; }
QScrollArea { border: none; }
QProgressBar { border: none; background: #e1e7da; border-radius: 3px; max-height: 6px; }
QProgressBar::chunk { background: #7a9d54; border-radius: 3px; }
QSplitter::handle { background: #dfe5de; width: 1px; }
QToolTip { background: #243128; color: #ffffff; padding: 6px; }
"""


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

    def __init__(self, pairs: list[PhotoPair], destination: Path):
        super().__init__()
        self.pairs = pairs
        self.destination = destination

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
            except Exception as exc:
                if claimed:
                    try:
                        path.unlink(missing_ok=True)
                    except OSError as cleanup_error:
                        errors.append(
                            f"Could not remove incomplete file {path.name}: {cleanup_error}"
                        )
                errors.append(f"{pair.filename}: {exc}")
            self.progress.emit(index, pair.filename)
        self.completed.emit(written, errors)


class CardMergerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.pairs: list[PhotoPair] = []
        self.input_folder: Path | None = None
        self.output_folder: Path | None = None
        self.thread: QThread | None = None
        self.worker: ExportWorker | None = None
        self.setWindowTitle("Card Merger")
        self.resize(1120, 800)
        self.setMinimumSize(780, 640)
        self.setStyleSheet(STYLE)
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
        work.addWidget(label("Check each pair, give it a name, then export.", "muted"))
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
            "Photos stay on your computer. Original files are preserved.", "muted", True
        )
        self.notice.setAccessibleName("Pair status")
        work.addWidget(self.notice)
        name_row = QHBoxLayout()
        field = QVBoxLayout()
        name_label = label("Card name")
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
        work.addLayout(name_row)
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
        bottom = QHBoxLayout()
        self.summary = label("Import photos to begin", "muted", True)
        bottom.addWidget(self.summary, 1)
        self.export_button = button("Export confirmed pairs", self.export_pairs, True)
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
        if pair:
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
                    else "Pair confirmed and ready to export."
                    if pair.confirmed
                    else "Verify both photos and enter the card name."
                )
            )
        confirmed = sum(p.confirmed and not p.skipped for p in self.pairs)
        skipped = sum(p.skipped for p in self.pairs)
        self.summary.setText(
            f"{confirmed} of {len(self.pairs)} pairs confirmed · {skipped} skipped"
            if self.pairs
            else "Import photos to begin"
        )
        self.export_button.setText(
            f"Export {confirmed} confirmed {'pair' if confirmed == 1 else 'pairs'}"
        )
        self.export_button.setEnabled(bool(confirmed and self.output_folder))

    def edit_name(self, text: str):
        if pair := self.current_pair:
            pair.name, pair.confirmed = text, False
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
            self.select_pair(self.queue.currentRow())

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
            self.select_pair(self.queue.currentRow())

    def skip_pair(self):
        if pair := self.current_pair:
            pair.skipped, pair.confirmed = not pair.skipped, False
            self.refresh()

    def export_pairs(self):
        pairs = [replace(p) for p in self.pairs if p.confirmed and not p.skipped]
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
                "Choose another output folder or change the card names. Existing files will not be overwritten.\n\n"
                + "\n".join(collisions[:10]),
            )
            return
        self.set_busy(True)
        self.progress.setRange(0, len(pairs))
        self.progress.setValue(0)
        self.thread = QThread(self)
        self.worker = ExportWorker(pairs, self.output_folder)
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
        self.progress.setVisible(busy)

    def export_progress(self, count: int, filename: str):
        self.progress.setValue(count)
        self.summary.setText(f"Exporting {filename}…")

    def export_complete(self, written: list[str], errors: list[str]):
        self.last_export = (written, errors)

    def export_finished(self):
        self.thread = self.worker = None
        self.set_busy(False)
        self.refresh()
        written, errors = self.last_export
        self.summary.setText(f"Export complete · {len(written)} saved · {len(errors)} failed")
        message = QMessageBox(self)
        message.setWindowTitle("Export complete")
        message.setText(f"{len(written)} merged PNG files saved.\n{len(errors)} pairs failed.")
        message.setInformativeText("Your original photos have been preserved.")
        message.setIcon(QMessageBox.Icon.Warning if errors else QMessageBox.Icon.Information)
        if errors:
            message.setDetailedText("\n".join(errors))
        show_folder = message.addButton("Open output folder", QMessageBox.ButtonRole.ActionRole)
        message.addButton(QMessageBox.StandardButton.Close)
        message.exec()
        if message.clickedButton() == show_folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output_folder)))

    def closeEvent(self, event: QCloseEvent):
        if self.thread:
            QMessageBox.information(
                self, "Export in progress", "Please wait for this export to finish before closing."
            )
            event.ignore()
        else:
            event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Card Merger")
    window = CardMergerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
