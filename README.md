# Pokémon Card Merger

## Desktop UI

Launch the PySide6 review workspace with [uv](https://docs.astral.sh/uv/):

```sh
uv run ui.py
```

Install the project dependencies with `uv sync`. Recognition models are loaded in a background worker when photos are imported, keeping the window responsive.

The window and Windows taskbar use `assets/app-icon.ico`, with sizes from 16 to 256 pixels. Editable artwork is in `assets/app-icon.svg`, with a PNG preview in `assets/app-icon.png`. Keep the `assets` folder beside `ui.py` when distributing the app.

1. Choose a folder containing JPG, PNG, WebP, BMP, or TIFF photos. Files are sorted by filename with numbers in numeric order, then grouped into consecutive front/back pairs.
2. Card names are recognized from the front photos automatically. Complete, readable, recognized pairs are confirmed automatically. You can edit any card name to override recognition, then confirm the pair again. If recognition fails, enter the name and confirm that pair. You can also swap sides, replace a missing back, or skip pairs. Swapping sides recognizes the new front again.
3. Choose a separate output folder and export confirmed pairs as side-by-side PNGs. If a filename already exists, an index is added (`Pikachu_1.png`, `Pikachu_2.png`, etc.). Existing files are never overwritten. **Delete input photos after successful export** is enabled by default: successfully exported originals in the input folder are permanently deleted. Uncheck it to keep originals. Failed/skipped pairs and replacement photos outside the input folder are kept; deletion problems are reported without removing the saved export.

Exports use full-resolution, orientation-corrected photographs, aligned at the top with white padding if their heights differ. Preview images are reduced in size only for display. Filenames follow `{card_name}.png`, preserving Japanese characters.

Recognition uses `recognize_image.py`; failures (including unavailable models) fall back to manual naming. Export uses the displayed name without running recognition again. Review state lasts for the current session.

The progress bar animates while recognition models and card hashes load, then tracks completed pairs. Reference hashes are cached in memory and reused across photos and folder imports until the app closes.

Run the UI checks after installing PySide6:

```sh
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v
```
