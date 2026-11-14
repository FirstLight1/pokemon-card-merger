"""Small, dependency-free model for the review workspace."""

import re
from dataclasses import dataclass
from pathlib import Path

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


@dataclass
class PhotoPair:
    index: int
    front: Path
    back: Path | None = None
    name: str = ""
    confirmed: bool = False
    skipped: bool = False
    error: str = ""
    exported: bool = False

    @property
    def filename(self) -> str:
        # Portable Windows/macOS/Linux filenames, including Japanese card names.
        name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", self.name).strip(" .")
        name = re.sub(r"\s+", "_", name)[:100] or "unknown"
        return f"{name}_pair_{self.index:03d}.png"

    @property
    def status(self) -> str:
        if self.skipped:
            return "Skipped"
        if self.error:
            return "Check image"
        if self.back is None:
            return "Missing back photo"
        if self.exported:
            return "Exported"
        return "Confirmed" if self.confirmed else "Needs review"


def load_pairs(folder: Path) -> list[PhotoPair]:
    """Natural filename order, then consecutive front/back photographs."""

    def natural_key(path: Path):
        return tuple(
            (1, int(part)) if part.isdigit() else (0, part.casefold())
            for part in re.split(r"(\d+)", path.name)
        ), path.name

    files = sorted(
        (p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES),
        key=natural_key,
    )
    return [
        PhotoPair(i // 2 + 1, files[i], files[i + 1] if i + 1 < len(files) else None)
        for i in range(0, len(files), 2)
    ]
