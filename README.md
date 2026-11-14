# Pokémon Card Merger

## Desktop UI

Launch the PySide6 review workspace with [uv](https://docs.astral.sh/uv/):

```sh
uv run ui.py
```

The script declares its own PySide6 dependency; launching the UI does not install or load the machine-learning dependencies. Alternatively, install `PySide6>=6.8,<7` and run `python ui.py`.

1. Choose a folder containing JPG, PNG, WebP, BMP, or TIFF photos. Files are sorted by filename with numbers in numeric order, then grouped into consecutive front/back pairs.
2. Review the previews, swap sides or replace a missing back, and enter a card name. Confirm each pair to include it in the export, or skip it.
3. Choose a separate output folder and export confirmed pairs as side-by-side PNGs. Existing files are never overwritten, and original photos are preserved.

Exports use full-resolution, orientation-corrected photographs, aligned at the top with white padding if their heights differ. Preview images are reduced in size only for display. Filenames follow `{card_name}_pair_{index}.png`, preserving Japanese characters.

Automatic recognition is not connected to this UI yet. The existing recognition script remains in `main.py`; the UI currently supports manual names and real image export. Review state lasts for the current session.

Run the UI checks after installing PySide6:

```sh
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v
```
