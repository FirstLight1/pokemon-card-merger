# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

This project is managed with `uv` (uv.lock present) and requires Python >= 3.14.

- Install / sync deps: `uv sync`
- Run the pipeline: `uv run python main.py`

There is no test suite, linter, or build step configured.

## External runtime dependencies

The script shells out to / depends on tools that are not Python packages and must be installed separately on the host:

- **Tesseract OCR** — `pytesseract` is just a wrapper; the `tesseract` binary must be on `PATH`.
- **ImageMagick** — `main()` invokes `magick ... +append` via `subprocess.run` to concatenate card images horizontally.

## Architecture

Single-file pipeline in `main.py` that pairs up card photos and stitches each pair into a combined image. The interesting part is the two-stage YOLO + OCR detection used to identify each card before merging:

1. **`findCardModel` (`findCard.pt`)** — first-stage YOLO model that locates the card itself within the input photo. The first detected box is cropped out as `crop_image`.
2. **`findNameModel` (`findNameNumber.pt`)** — second-stage YOLO model run on the cropped card. It emits boxes with class labels; `getName()` filters for the `"name"` class and returns that sub-region as `namePlate`.
3. **`extractText`** — resizes the name plate to 200×70 and runs Tesseract with `--psm 7` (single line) and an alphabetic-only whitelist to read the card's name.
4. **Merge step** — `subprocess.run(["magick", img1, img2, "+append", "$outFile"], ...)` concatenates the pair side-by-side.

Both `.pt` weights files live at the repo root and are loaded at import time, so changes there affect every run.

### Things to know before editing `main.py`

- `selectFolder()` hardcodes Windows paths under `C:\Users\kamen\Pictures\cardinput` and `...\cardoutput`. These must exist or be changed before running.
- The merge subprocess call has bugs the code currently lives with: it passes `img1`/`img2` (numpy arrays read by `cv2.imread`) where ImageMagick expects file paths, and `"$outFile"` is a literal string, not an interpolated variable. Treat this line as unfinished.
- `getName()` references a global `names` lookup that isn't defined in this file — likely intended to be `result.names` from the YOLO result. The first call also blocks on `cv2.waitKey()` for every image, which is debug-only behavior.
- The main loop iterates files two at a time (`range(0, len(files), 2)`), so an odd file count drops the last image.
