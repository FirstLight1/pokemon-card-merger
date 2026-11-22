"""Conservative cleanup of PyInstaller's Windows binary table."""

from pathlib import PureWindowsPath


def deduplicate_dlls(binaries):
    """Drop root DLL copies only when the identical source stays in its package.

    PyTorch and delvewheel-managed NumPy/SciPy load their DLLs from their own
    directories. PyInstaller can additionally collect those files at the root.
    Never merge different source files merely because their names match.
    """
    packaged_sources = {
        str(PureWindowsPath(source)).casefold()
        for destination, source, kind in binaries
        if kind == "BINARY" and len(PureWindowsPath(destination).parts) > 1
    }
    return [
        entry
        for entry in binaries
        if not (
            entry[2] == "BINARY"
            and len(PureWindowsPath(entry[0]).parts) == 1
            and PureWindowsPath(entry[0]).suffix.lower() == ".dll"
            and str(PureWindowsPath(entry[1])).casefold() in packaged_sources
        )
    ]
