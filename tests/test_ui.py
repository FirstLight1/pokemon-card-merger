"""Real Qt image and UI checks; no model weights or source photographs needed."""

import os
import tempfile
import time
import unittest
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from recognition_backend import get_recognizer
from ui import THEMES, CardMergerWindow, ExportWorker, read_image, recognize_name
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
        self.recognizer = patch("ui.recognize_name", side_effect=ValueError("No match"))
        self.recognizer.start()
        self.addCleanup(self.recognizer.stop)
        self.initializer = patch("ui.initialize_recognition")
        self.initializer.start()
        self.addCleanup(self.initializer.stop)

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
        self.wait_for_worker()
        return self.window

    def wait_for_worker(self):
        for _ in range(500):
            self.app.processEvents()
            if self.window.thread is None:
                return
            time.sleep(0.01)
        self.fail("Background worker did not finish")

    def run_export(self, pairs):
        worker = ExportWorker(pairs, self.output)
        results = []
        worker.completed.connect(lambda written, errors: results.extend([written, errors]))
        worker.run()
        return results

    def test_dark_theme_is_default_and_button_switches_both_ways(self):
        window = self.make_window()
        self.assertEqual(window.theme, "dark")
        dark_style = window.styleSheet()
        self.assertIn(THEMES["dark"]["background"], dark_style)
        self.assertEqual(window.theme_button.text(), "☀")
        self.assertEqual(THEMES["dark"]["background"], "#0E0E0E")
        self.assertEqual(THEMES["dark"]["text"], "#FFFFFF")
        self.assertEqual(THEMES["dark"]["muted"], "#A3A3A3")
        self.assertEqual(THEMES["dark"]["accent"], "#22C55E")
        self.assertEqual(THEMES["dark"]["primary"], "#22C55E")
        QTest.mouseClick(window.theme_button, Qt.MouseButton.LeftButton)
        self.assertEqual(window.theme, "light")
        self.assertIn(THEMES["light"]["background"], window.styleSheet())
        self.assertEqual(window.theme_button.accessibleName(), "Switch to dark mode")
        self.assertEqual(window.theme_button.text(), "☾")
        QTest.mouseClick(window.theme_button, Qt.MouseButton.LeftButton)
        self.assertEqual(window.theme, "dark")
        self.assertEqual(window.styleSheet(), dark_style)

    def test_window_icon_loads_outside_the_project_directory(self):
        previous_directory = Path.cwd()
        try:
            os.chdir(self.folder)
            self.window = CardMergerWindow()
            icon = self.window.windowIcon()
            self.assertFalse(icon.isNull())
            sizes = {size.width() for size in icon.availableSizes()}
            self.assertTrue({16, 32, 48, 256}.issubset(sizes))
        finally:
            os.chdir(previous_directory)

    def test_theme_switch_preserves_review_and_works_while_busy(self):
        self.photo("IMG_1.png")
        self.photo("IMG_2.png")
        window = self.make_window()
        QTest.keyClicks(window.name, "Pikachu")
        window.confirm_pair()
        pair = window.current_pair
        window.set_busy(True)
        try:
            self.assertTrue(window.theme_button.isEnabled())
            QTest.mouseClick(window.theme_button, Qt.MouseButton.LeftButton)
            self.assertEqual(window.theme, "light")
            self.assertIs(window.current_pair, pair)
            self.assertEqual(window.name.text(), "Pikachu")
            self.assertTrue(pair.confirmed)
            self.assertFalse(window.splitter.isEnabled())
        finally:
            window.set_busy(False)

    def test_export_button_is_neon_green_only_when_export_is_available(self):
        self.photo("IMG_1.png")
        self.photo("IMG_2.png")
        window = self.make_window()
        for theme in ("dark", "light"):
            window.set_theme(theme)
            window.output_folder = None
            window.refresh()
            self.app.processEvents()
            self.assertFalse(window.export_button.isEnabled())
            self.assertNotEqual(
                window.export_button.palette().color(QPalette.ColorRole.Button), QColor("#22C55E")
            )
            window.edit_name("Pikachu")
            window.confirm_pair()
            window.output_folder = self.output
            window.refresh()
            self.app.processEvents()
            self.assertTrue(window.export_button.isEnabled())
            self.assertEqual(
                window.export_button.palette().color(QPalette.ColorRole.Button), QColor("#22C55E")
            )

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
        self.assertEqual(pair.filename, "ピカチュウ.png")
        pair.name = "..."
        self.assertEqual(pair.filename, "unknown.png")

    def test_review_edit_swap_and_skip_invalidate_confirmation(self):
        self.photo("IMG_1.png")
        self.photo("IMG_2.png", color=Qt.GlobalColor.blue)
        window = self.make_window()
        self.assertFalse(window.confirm_button.isEnabled())
        QTest.keyClicks(window.name, "Pikachu")
        QTest.mouseClick(window.confirm_button, Qt.MouseButton.LeftButton)
        self.assertTrue(window.current_pair.confirmed)
        QTest.mouseClick(window.swap_button, Qt.MouseButton.LeftButton)
        self.wait_for_worker()
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
            self.wait_for_worker()
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
        pairs = [PhotoPair(i, front, back, name=f"Pikachu{i}", confirmed=True) for i in (1, 2)]
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
        window.delete_after_export.setChecked(False)
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

    def test_default_export_deletes_only_successful_input_photos(self):
        for index in range(1, 7):
            self.photo(f"IMG_{index}.png")
        with patch("ui.recognize_name", return_value="Pikachu"):
            window = self.make_window()
        self.assertTrue(window.delete_after_export.isChecked())
        window.output_folder = self.output
        window.pairs[2].skipped = True
        window.pairs[1].back.write_bytes(b"broken")
        with patch.object(QMessageBox, "exec", return_value=0):
            window.export_pairs()
            self.assertFalse(window.delete_after_export.isEnabled())
            self.wait_for_worker()
        self.assertTrue(window.delete_after_export.isEnabled())
        self.assertTrue(window.pairs[0].exported)
        self.assertFalse(window.pairs[0].front.exists())
        self.assertFalse(window.pairs[0].back.exists())
        for pair in window.pairs[1:]:
            self.assertTrue(pair.front.exists())
            self.assertTrue(pair.back.exists())
        window.select_pair(0)
        self.assertEqual(window.current_pair.status, "Exported")
        self.assertFalse(window.current_pair.error)
        self.assertEqual(len(window.last_export[0]), 1)
        self.assertEqual(len(window.last_export[1]), 1)

    def test_disabling_deletion_keeps_input_photos(self):
        front, back = self.photo("IMG_1.png"), self.photo("IMG_2.png")
        with patch("ui.recognize_name", return_value="Pikachu"):
            window = self.make_window()
        window.delete_after_export.setChecked(False)
        window.output_folder = self.output
        with patch.object(QMessageBox, "exec", return_value=0):
            window.export_pairs()
            self.wait_for_worker()
        self.assertTrue(front.exists())
        self.assertTrue(back.exists())

    def test_deletion_keeps_external_replacement_and_shared_photos(self):
        front = self.photo("IMG_1.png")
        external = self.folder / "replacement.png"
        external.write_bytes(front.read_bytes())
        worker = ExportWorker([
            PhotoPair(1, front, external, name="Pikachu"),
            PhotoPair(2, front, external, name="Eevee"),
        ], self.output, True, self.source)
        worker.run()
        self.assertEqual(worker.written_pair_indices, {1, 2})
        self.assertFalse(front.exists())
        self.assertTrue(external.exists())

    def test_deletion_failure_preserves_successful_export(self):
        front, back = self.photo("IMG_1.png"), self.photo("IMG_2.png")
        worker = ExportWorker([PhotoPair(1, front, back, name="Pikachu")],
                              self.output, True, self.source)
        with patch.object(Path, "unlink", side_effect=PermissionError("access denied")):
            worker.run()
        self.assertEqual(worker.written_pair_indices, {1})
        self.assertEqual(len(worker.cleanup_errors), 2)
        self.assertTrue(front.exists())
        self.assertTrue(back.exists())
        self.assertFalse(read_image(self.output / "Pikachu.png").isNull())

    def test_failed_export_protects_shared_input_photo(self):
        front, back = self.photo("IMG_1.png"), self.photo("IMG_2.png")
        worker = ExportWorker([
            PhotoPair(1, front, back, name="Pikachu"),
            PhotoPair(2, front, self.source / "missing.png", name="Eevee"),
        ], self.output, True, self.source)
        worker.run()
        self.assertEqual(worker.written_pair_indices, {1})
        self.assertTrue(front.exists())
        self.assertFalse(back.exists())

    def test_cleanup_error_counts_as_one_failed_pair(self):
        front = self.photo("IMG_1.png")
        pair = PhotoPair(1, front, self.source / "missing.png", name="Pikachu")
        with patch.object(Path, "unlink", side_effect=OSError("cleanup denied")):
            written, errors = self.run_export([pair])
        self.assertEqual(written, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("Cannot open", errors[0])
        self.assertIn("cleanup denied", errors[0])

    def test_recognized_pairs_are_automatically_confirmed_without_name_input(self):
        for index in range(1, 5):
            self.photo(f"IMG_{index}.png")
        with patch("ui.recognize_name", side_effect=["Pikachu", "Eevee"]):
            window = self.make_window()
        self.assertEqual([p.name for p in window.pairs], ["Pikachu", "Eevee"])
        self.assertTrue(all(p.confirmed for p in window.pairs))
        self.assertFalse(window.manual_naming.isHidden())
        self.assertIn("Pikachu", window.recognized_name.text())
        window.output_folder = self.output
        window.refresh()
        self.assertTrue(window.export_button.isEnabled())

    def test_recognized_name_can_be_overridden_and_exported_after_confirmation(self):
        for index in range(1, 5):
            self.photo(f"IMG_{index}.png")
        with patch("ui.recognize_name", side_effect=["Pikachu", "Eevee"]):
            window = self.make_window()
        window.output_folder = self.output
        window.current_pair.exported = True
        window.name.selectAll()
        QTest.keyClicks(window.name, "Raichu")
        pair = window.current_pair
        self.assertEqual(pair.name, "Raichu")
        self.assertFalse(pair.confirmed)
        self.assertFalse(pair.exported)
        self.assertIn("Confirm this pair", window.notice.text())
        self.assertEqual(window.filename.text(), "Raichu.png")
        self.assertIn("Raichu", window.queue.item(0).text())
        window.queue.setCurrentRow(1)
        window.queue.setCurrentRow(0)
        self.assertEqual(window.name.text(), "Raichu")
        QTest.mouseClick(window.confirm_button, Qt.MouseButton.LeftButton)
        self.assertTrue(pair.confirmed)
        written, errors = self.run_export([pair])
        self.assertEqual(errors, [])
        self.assertEqual(written, [str(self.output / "Raichu.png")])

    def test_failed_recognition_shows_manual_input_for_failed_pair(self):
        for index in range(1, 5):
            self.photo(f"IMG_{index}.png")
        with patch("ui.recognize_name", side_effect=["Pikachu", ValueError("No match")]):
            window = self.make_window()
        window.queue.setCurrentRow(1)
        self.assertFalse(window.manual_naming.isHidden())
        self.assertFalse(window.current_pair.confirmed)
        QTest.keyClicks(window.name, "Eevee")
        window.confirm_pair()
        self.assertTrue(window.current_pair.confirmed)
        self.assertEqual(window.current_pair.name, "Eevee")

    def test_recognized_missing_or_broken_photos_are_not_confirmed(self):
        self.photo("IMG_1.png")
        (self.source / "IMG_2.png").write_bytes(b"broken")
        self.photo("IMG_3.png")
        with patch("ui.recognize_name", return_value="Pikachu"):
            window = self.make_window()
        self.assertTrue(all(not p.confirmed for p in window.pairs))
        self.assertIn("Cannot open", window.pairs[0].error)
        self.assertIsNone(window.pairs[1].back)

    def test_swapping_front_reruns_recognition(self):
        self.photo("IMG_1.png")
        self.photo("IMG_2.png")
        with patch("ui.recognize_name", side_effect=["Pikachu", "Eevee"]) as recognize:
            window = self.make_window()
            window.swap_sides()
            self.wait_for_worker()
        self.assertEqual(window.current_pair.name, "Eevee")
        self.assertTrue(window.current_pair.confirmed)
        self.assertEqual(recognize.call_args.args[0].name, "IMG_2.png")

    def test_recognizer_filename_is_normalized_once(self):
        with patch.dict("sys.modules", {"recognize_image": SimpleNamespace(
            hash_recognize=lambda *_: "Pikachu_025.png"
        )}):
            name = recognize_name(Path("front.png"))
        self.assertEqual(name, "Pikachu_025")
        self.assertEqual(PhotoPair(1, Path("front.png"), name=name).filename, "Pikachu_025.png")

    def test_hash_loading_shows_busy_bar_and_keeps_ui_events_running(self):
        self.photo("IMG_1.png")
        self.photo("IMG_2.png")
        release = Event()

        def initialize(report):
            report("Loading card hashes…", 0)
            if not release.wait(5):
                raise TimeoutError("Test did not release initialization")

        with patch("ui.initialize_recognition", side_effect=initialize), patch(
            "ui.recognize_name", return_value="Pikachu"
        ):
            self.window = CardMergerWindow()
            self.window.show()
            self.window.load_folder(self.source)
            try:
                for _ in range(100):
                    self.app.processEvents()
                    if self.window.summary.text() == "Loading card hashes…":
                        break
                    time.sleep(0.01)
                self.assertEqual(self.window.summary.text(), "Loading card hashes…")
                self.assertEqual(self.window.progress.maximum(), 0)
                self.assertTrue(self.window.progress.isVisible())
                self.assertIsNotNone(self.window.thread)
                self.assertFalse(self.window.export_button.isEnabled())
            finally:
                release.set()
                self.wait_for_worker()
        self.assertTrue(self.window.current_pair.confirmed)
        self.assertFalse(self.window.progress.isVisible())
        self.assertEqual(self.window.progress.maximum(), 1)

    def test_hash_loading_failure_falls_back_to_manual_names(self):
        self.photo("IMG_1.png")
        self.photo("IMG_2.png")
        with patch("ui.initialize_recognition", side_effect=OSError("Database unavailable")):
            window = self.make_window()
        self.assertTrue(window.current_pair.recognition_failed)
        self.assertEqual(window.current_pair.recognition_error, "Database unavailable")
        self.assertFalse(window.manual_naming.isHidden())
        self.assertFalse(window.progress.isVisible())

    def test_hashes_are_loaded_once_and_reused_across_photos(self):
        loads = []

        class FakeRecognizer:
            def _get_cards(self):
                loads.append(True)
                return ["reference hash"]

            def recognize(self, image):
                return self._get_cards()

        get_recognizer.cache_clear()
        try:
            with patch.dict("sys.modules", {
                "tcg_card_recognizer": SimpleNamespace(Recognizer=FakeRecognizer)
            }):
                recognizer = get_recognizer()
                self.assertEqual(recognizer.recognize(b"first"), ["reference hash"])
                self.assertEqual(recognizer.recognize(b"second"), ["reference hash"])
                self.assertIs(get_recognizer(), recognizer)
                self.assertEqual(len(loads), 1)
        finally:
            get_recognizer.cache_clear()


if __name__ == "__main__":
    unittest.main()
