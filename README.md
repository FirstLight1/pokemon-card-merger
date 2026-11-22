# Pokémon Card Merger

## Desktop UI

Launch the PySide6 review workspace with [uv](https://docs.astral.sh/uv/):

```sh
uv run ui.py
```

Install the project dependencies with `uv sync`. Recognition models are loaded in a background worker when photos are imported, keeping the window responsive.

1. Choose a folder containing JPG, PNG, WebP, BMP, or TIFF photos. Files are sorted by filename with numbers in numeric order, then grouped into consecutive front/back pairs.
2. Card names are recognized from the front photos automatically. Complete, readable, recognized pairs are confirmed automatically. Only failed recognition shows a name field: enter the name and confirm that pair. You can also swap sides, replace a missing back, or skip pairs. Swapping sides recognizes the new front again.
3. Choose a separate output folder and export confirmed pairs as side-by-side PNGs. Existing files are never overwritten, and original photos are preserved.

Exports use full-resolution, orientation-corrected photographs, aligned at the top with white padding if their heights differ. Preview images are reduced in size only for display. Filenames follow `{card_name}.png`, preserving Japanese characters.

Recognition uses `recognize_image.py`; failures (including unavailable models) fall back to manual naming. Export uses the displayed name without running recognition again. Review state lasts for the current session.

Run the UI checks after installing PySide6:

```sh
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v
```
