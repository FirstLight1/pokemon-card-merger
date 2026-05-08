import os
import sys
import cv2
import easyocr
from pathlib import Path

from main import (
    cardBorders,
    findCardModel,
    findNameModel,
    getName,
    preprocessImage,
)

INPUT_DIR = r"C:\Users\kamen\Pictures\cardinput"
OUT_DIR = Path("debug")

_reader = None
def get_reader():
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(["ja", "en"])
    return _reader


def process(image_path):
    image_path = Path(image_path)
    name = image_path.stem
    out = OUT_DIR / name
    out.mkdir(parents=True, exist_ok=True)

    img = cv2.imread(str(image_path))
    if img is None:
        print(f"[skip] could not load {image_path}")
        return

    try:
        results = findCardModel(img)
    except Exception as e:
        print(f"[skip] findCardModel failed on {name}: {e}")
        return

    for card in results:
        if len(card.boxes.xyxy) == 0:
            print(f"[skip] no card detected in {name}")
            return

        x1, y1, x2, y2 = cardBorders(card.boxes.xyxy[0])
        crop = img[y1:y2, x1:x2]
        cv2.imwrite(str(out / "1_crop.png"), crop)

        try:
            cardName = findNameModel(crop)
            namePlate = getName(cardName[0], crop)
        except Exception as e:
            print(f"[skip] name detection failed on {name}: {e}")
            return

        cv2.imwrite(str(out / "2_nameplate.png"), namePlate)

        big = cv2.resize(namePlate, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
        hsv = cv2.cvtColor(big, cv2.COLOR_BGR2HSV)
        cv2.imwrite(str(out / "2a_v.png"), hsv[:, :, 2])
        cv2.imwrite(str(out / "2b_s.png"), hsv[:, :, 1])
        _, raw_inv = cv2.threshold(hsv[:, :, 2], 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
        cv2.imwrite(str(out / "2c_raw_inv.png"), raw_inv)
        _, raw_bin = cv2.threshold(hsv[:, :, 2], 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        cv2.imwrite(str(out / "2d_raw_bin.png"), raw_bin)

        processed = preprocessImage(namePlate)
        cv2.imwrite(str(out / "3_processed.png"), processed)
        allowlist = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz' "

        big = cv2.resize(namePlate, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

        lab = cv2.cvtColor(big, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        clahe_img = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)
        cv2.imwrite(str(out / "4_clahe.png"), clahe_img)

        gray = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)
        gray_clahe = clahe.apply(gray)
        cv2.imwrite(str(out / "5_gray_clahe.png"), gray_clahe)

        t1 = get_reader().readtext(big, allowlist=allowlist, detail=0, paragraph=True)
        t2 = get_reader().readtext(clahe_img, allowlist=allowlist, detail=0, paragraph=True)
        t3 = get_reader().readtext(gray_clahe, allowlist=allowlist, detail=0, paragraph=True)
        print(f"[ok] {name}")
        print(f"   color 3x      : {t1}")
        print(f"   color 3x clahe: {t2}")
        print(f"   gray  3x clahe: {t3}")
        return


def main():
    OUT_DIR.mkdir(exist_ok=True)
    args = sys.argv[1:]

    if not args:
        targets = [
            os.path.join(INPUT_DIR, f)
            for f in sorted(os.listdir(INPUT_DIR))
            if f.lower().endswith((".jpg", ".jpeg", ".png"))
        ]
    else:
        targets = [a if os.path.exists(a) else os.path.join(INPUT_DIR, a) for a in args]

    for t in targets:
        process(t)


if __name__ == "__main__":
    main()
