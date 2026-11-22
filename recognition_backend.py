"""Load the recognizer's reference hashes once, on the recognition worker thread."""

from functools import cache


@cache
def get_recognizer():
    from tcg_card_recognizer import Recognizer

    class CachedRecognizer(Recognizer):
        # The dependency normally queries SQLite for every photograph. Keep its
        # matching implementation, but reuse the read-only reference data.
        def __init__(self):
            super().__init__()
            self._cards = super()._get_cards()

        def _get_cards(self):
            return self._cards

    recognizer = CachedRecognizer()
    return recognizer
