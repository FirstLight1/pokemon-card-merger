from PIL import Image
from ultralytics import YOLO
import cv2
import numpy as np
import time
import os
import subprocess
from pathlib import Path
import math
import re
from recognition_backend import get_recognizer

findCardModel = YOLO(str(Path(__file__).resolve().parent / "findCard.pt"))

names = {
    0: "Name",
    1: "Number"
}

def cardBorders(result):
    x1 = result[0]
    y1 = result[1]
    x2 = result[2]
    y2 = result[3]
    return int(x1), int(y1), int(x2), int(y2)


def selectFolder():
    inputFolder = r"C:\Users\kamen\Pictures\cardinput"
    outputFolder = r"C:\Users\kamen\Pictures\cardoutput"
    return inputFolder, outputFolder

def getStartIndex(output):
    existing = [int(match.group(1))
    for f in Path(output).glob('*pair_*.png')
    if (match := re.match(r'.*pair_(\d+)\.png', f.name))]

    if existing:
        return max(existing) + 1
    else:
        return 1

def hash_recognize(img, img_path) -> str:
    results = []
    img = str(img)
    image = cv2.imread(img)
    try:
        results = findCardModel(image)
    except:
        raise Exception("failed to find card")
        print("failed to find card" + img_path)
    for card in results:
        flatTensor = card.boxes.xyxy[0]
        x1,y1,x2,y2 = cardBorders(flatTensor)
        crop_image = image[y1:y2,x1:x2]
        success, encoded = cv2.imencode(".png", crop_image)
        if not success:
            raise ValueError("Failed to encode crop")
        image_bytes = encoded.tobytes()

        recognizer = get_recognizer()
        result = recognizer.recognize(image_bytes, 5)
        namePlateStr = result[0][2] + result[0][3]
        file_name = (namePlateStr).replace(" ", "_")
        return file_name

def main():
    input, output = selectFolder()

    value = getStartIndex(output)
    startIndex = value
    
    pattern = re.compile(r'IMG_(\d+)\.(jpe?g|png|heic)$', re.IGNORECASE)
    files = sorted(
        (f for f in os.listdir(input) if pattern.match(f)),
        key=lambda f: int(pattern.match(f).group(1)),
    )
    for i in range(0, len(files),2):
        pairIndex = startIndex + math.floor(i/2)
 
        if(i + 1 < len(files)):
            img1Path = os.path.join(input, files[i])
            print(img1Path)
            img1 = cv2.imread(img1Path)
            
            img2Path = os.path.join(input, files[i + 1])
            out_file = hash_recognize(img1Path, img1Path)

            try:
                subprocess.run(["magick", img1Path, img2Path, "+append", out_file], capture_output=True, text=True)
                print("images merged succesfully")
                #os.remove(img1Path)
                #os.remove(img2Path)
            except:
                print("error merging images")
        else:
            pass



if __name__ == "__main__":
    main()
