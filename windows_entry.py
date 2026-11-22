"""Windowed executable entry point and packaged-build smoke check."""

import multiprocessing
import os
import sys
from pathlib import Path


def main():
    multiprocessing.freeze_support()
    # Windowed executables have no console. Keep library diagnostics available.
    if sys.stdout is None or sys.stderr is None:
        log_folder = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "PokemonCardMerger"
        log_folder.mkdir(parents=True, exist_ok=True)
        log = (log_folder / "app.log").open("a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log

    if len(sys.argv) == 3 and sys.argv[1] == "--smoke-test":
        import json
        import traceback

        report = {}
        try:
            import numpy as np
            from PySide6.QtWidgets import QApplication

            from ui import APP_ICON_PATH, CardMergerWindow

            app = QApplication([])
            window = CardMergerWindow()
            assert APP_ICON_PATH.is_file()
            assert not window.windowIcon().isNull()
            window.show()
            app.processEvents()
            from recognition_backend import get_recognizer
            from recognize_image import findCardModel

            findCardModel.predict(np.zeros((640, 640, 3), dtype=np.uint8), verbose=False)
            recognizer = get_recognizer()
            assert recognizer._get_cards()
            from io import BytesIO

            from PIL import Image

            image = BytesIO()
            Image.new("RGB", (200, 279), "white").save(image, format="PNG")
            assert recognizer.recognize(image.getvalue(), 1)
            report = {"ok": True, "cards": len(recognizer._get_cards())}
            window.close()
        except Exception:
            report = {"ok": False, "error": traceback.format_exc()}
        Path(sys.argv[2]).write_text(json.dumps(report, indent=2), encoding="utf-8")
        return 0 if report["ok"] else 1

    from ui import main as run_ui

    run_ui()
    return 0


if __name__ == "__main__":
    sys.exit(main())
