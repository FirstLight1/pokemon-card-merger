"""Real Qt image and UI checks; no model weights or source photographs needed."""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from ui import CardMergerWindow, ExportWorker, read_image
from ui_model import PhotoPair, load_pairs


class WorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.source = self.folder / "input"
        self.output = self.folder / "output"
        self.source.mkdir()
        self.output.mkdir()
        self.window = None

    def tearDown(self):
        if self.window:
            self.window.close()
        self.temp.cleanup()

    def photo(self, name, width=80, height=120, color=Qt.GlobalColor.red):
        path = self.source / name
        image = QImage(width, height, QImage.Format.Format_RGB32)
        image.fill(color)
        self.assertTrue(image.save(str(path)))
        return path

    def make_window(self):
        self.window = CardMergerWindow()
        self.window.show()
        self.window.load_folder(self.source)
        self.app.processEvents()
        return self.window

    def run_export(self, pairs):
        worker = ExportWorker(pairs, self.output)
        results = []
        worker.completed.connect(lambda written, errors: results.extend([written, errors]))
        worker.run()
        return results

    def test_numeric_pairing_keeps_odd_image_and_ignores_other_files(self):
        for name in ["IMG_11.png", "IMG_2.png", "IMG_3.png"]:
            self.photo(name)
        (self.source / "notes.txt").write_text("ignore")
        pairs = load_pairs(self.source)
        self.assertEqual([p.front.name for p in pairs], ["IMG_2.png", "IMG_11.png"])
        self.assertEqual(pairs[0].back.name, "IMG_3.png")
        self.assertEqual(pairs[1].status, "Missing back photo")

    def test_filename_preserves_japanese_and_removes_unsafe_characters(self):
        pair = PhotoPair(3, Path("front.jpg"), name=' ピカチュウ / : * ? " <> | \\ ')
        self.assertEqual(pair.filename, "ピカチュウ_pair_003.png")
        pair.name = "..."
        self.assertEqual(pair.filename, "unknown_pair_003.png")

    def test_review_edit_swap_and_skip_invalidate_confirmation(self):
        self.photo("IMG_1.png")
        self.photo("IMG_2.png", color=Qt.GlobalColor.blue)
        window = self.make_window()
        self.assertFalse(window.confirm_button.isEnabled())
        QTest.keyClicks(window.name, "Pikachu")
        QTest.mouseClick(window.confirm_button, Qt.MouseButton.LeftButton)
        self.assertTrue(window.current_pair.confirmed)
        QTest.mouseClick(window.swap_button, Qt.MouseButton.LeftButton)
        self.assertEqual(window.current_pair.front.name, "IMG_2.png")
        self.assertFalse(window.current_pair.confirmed)
        window.confirm_pair()
        QTest.keyClicks(window.name, " ex")
        self.assertFalse(window.current_pair.confirmed)
        window.confirm_pair()
        window.skip_pair()
        self.assertFalse(window.current_pair.confirmed)
        self.assertFalse(window.name.isEnabled())
        self.assertFalse(window.confirm_button.isEnabled())
        window.skip_pair()
        self.assertTrue(window.name.isEnabled())

    def test_replacing_batch_and_loading_empty_folder(self):
        self.photo("IMG_1.png")
        self.photo("IMG_2.png")
        window = self.make_window()
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            window.load_folder(self.source)
            self.assertEqual(window.queue.count(), 1)
            window.load_folder(self.output)
        self.assertEqual(window.queue.count(), 0)
        self.assertFalse(window.name.isEnabled())

    def test_missing_or_unreadable_photo_blocks_confirmation(self):
        self.photo("IMG_1.png")
        window = self.make_window()
        window.edit_name("Pikachu")
        window.confirm_pair()
        self.assertFalse(window.current_pair.confirmed)
        broken = self.source / "broken.png"
        broken.write_bytes(b"not a photo")
        window.current_pair.back = broken
        window.select_pair(0)
        self.assertIn("Cannot open", window.current_pair.error)
        self.assertFalse(window.confirm_button.isEnabled())

    def test_export_keeps_full_resolution_colors_and_source_files(self):
        front = self.photo("IMG_1.png", 80, 120)
        back = self.photo("IMG_2.png", 60, 100, Qt.GlobalColor.blue)
        originals = [front.read_bytes(), back.read_bytes()]
        pair = PhotoPair(1, front, back, name="Pikachu", confirmed=True)
        written, errors = self.run_export([pair])
        self.assertFalse(errors)
        self.assertEqual(len(written), 1)
        merged = read_image(Path(written[0]))
        self.assertEqual((merged.width(), merged.height()), (140, 120))
        self.assertEqual(merged.pixelColor(0, 0), Qt.GlobalColor.red)
        self.assertEqual(merged.pixelColor(80, 0), Qt.GlobalColor.blue)
        self.assertEqual(merged.pixelColor(139, 119), Qt.GlobalColor.white)
        self.assertEqual([front.read_bytes(), back.read_bytes()], originals)

    def test_export_refuses_existing_file_and_continues_after_failure(self):
        front = self.photo("IMG_1.png")
        back = self.photo("IMG_2.png")
        pairs = [PhotoPair(i, front, back, name="Pikachu", confirmed=True) for i in (1, 2)]
        existing = self.output / pairs[0].filename
        existing.write_bytes(b"existing contents")
        written, errors = self.run_export(pairs)
        self.assertEqual(existing.read_bytes(), b"existing contents")
        self.assertEqual(len(written), 1)
        self.assertEqual(len(errors), 1)

    def test_partial_export_retries_only_failed_pairs(self):
        for index in range(1, 5):
            self.photo(f"IMG_{index}.png")
        window = self.make_window()
        window.output_folder = self.output
        for row in range(2):
            window.queue.setCurrentRow(row)
            window.edit_name(f"Card{row}")
            window.confirm_pair()
        missing = window.pairs[1].back
        missing.unlink()

        def export():
            with patch.object(QMessageBox, "exec", return_value=0):
                window.export_pairs()
                self.assertFalse(window.import_button.isEnabled())
                for _ in range(200):
                    time.sleep(0.01)
                    self.app.processEvents()
                    if window.thread is None:
                        break
                self.assertIsNone(window.thread)
                self.assertTrue(window.import_button.isEnabled())

        export()
        self.assertTrue(window.pairs[0].exported)
        self.assertFalse(window.pairs[1].exported)
        self.assertEqual(len(window.last_export[1]), 1)
        self.assertFalse((self.output / window.pairs[1].filename).exists())
        original = (self.output / window.pairs[0].filename).read_bytes()
        self.photo(missing.name)
        export()
        self.assertEqual(len(window.last_export[0]), 1)
        self.assertEqual(window.last_export[1], [])
        self.assertTrue(all(pair.exported for pair in window.pairs))
        self.assertFalse(window.export_button.isEnabled())
        self.assertEqual((self.output / window.pairs[0].filename).read_bytes(), original)
        window.skip_pair()
        window.skip_pair()
        window.confirm_pair()
        self.assertFalse(window.export_button.isEnabled())
        window.edit_name("New name")
        window.confirm_pair()
        self.assertFalse(window.current_pair.exported)
        self.assertTrue(window.export_button.isEnabled())
        export()
        self.assertEqual(len(window.last_export[0]), 1)
        self.assertEqual(window.last_export[1], [])

    def test_cleanup_error_counts_as_one_failed_pair(self):
        front = self.photo("IMG_1.png")
        pair = PhotoPair(1, front, self.source / "missing.png", name="Pikachu")
        with patch.object(Path, "unlink", side_effect=OSError("cleanup denied")):
            written, errors = self.run_export([pair])
        self.assertEqual(written, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("Cannot open", errors[0])
        self.assertIn("cleanup denied", errors[0])


if __name__ == "__main__":
    unittest.main()
