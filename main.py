from PIL import Image
import easyocr
from ultralytics import YOLO
import cv2
import numpy as np
import time
import os
import subprocess
from pathlib import Path
import math
import re

findCardModel = YOLO("findCard.pt")
findNameModel = YOLO("findNameNumber.pt")

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

def getName(result, img):
    boxes = result.boxes.xyxy
    class_ids = result.boxes.cls

    for box, cls_id in zip(boxes, class_ids):
        class_name = names[int(cls_id)]
        if class_name.lower() == "name":
            x1, y1, x2, y2 = cardBorders(box)
            namePlate = img[y1:y2, x1:x2]

    return namePlate

def preprocessImage(img):
    img = cv2.resize(img, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)

    v_smooth = cv2.bilateralFilter(v, 7, 25, 25)
    _, th = cv2.threshold(v_smooth, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    return th

def extractText(img, reader):
    img = preprocessImage(img)
    cv2.imshow('extract', img)
    cv2.waitKey()
    text = reader.readtext(img, allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz', detail=0, paragraph=True)
    return text

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

def main():
    input, output = selectFolder()

    value = getStartIndex(output)
    startIndex = value
    
    pattern = re.compile(r'IMG_(\d+)\.(jpe?g|png|heic)$', re.IGNORECASE)
    files = sorted(
        (f for f in os.listdir(input) if pattern.match(f)),
        key=lambda f: int(pattern.match(f).group(1)),
    )
    print(files)
    reader = easyocr.Reader(['ja','en'])
    for i in range(0, len(files),2):
        pairIndex = startIndex + math.floor(i/2)
 
        if(i + 1 < len(files)):
            img1Path = os.path.join(input, files[i])
            img1 = cv2.imread(img1Path)
            
            img2Path = os.path.join(input, files[i + 1])
            try:
                results = findCardModel(img1)
            except:
                print("failed to find card" + img1Path)
            for card in results:
                
                print(img1Path)
                flatTensor = card.boxes.xyxy[0]
                x1,y1,x2,y2 = cardBorders(flatTensor)

                crop_image = img1[y1:y2,x1:x2]
                #try:
                if True:
                    cardName = findNameModel(crop_image)

                    namePlate = getName(cardName[0], crop_image)
                    namePlateStr = extractText(namePlate, reader)
                    print("output")
                    print(namePlateStr)
                    outFile = os.path.join(output, namePlateStr + f"_pair_{pairIndex}.png") 
                #except:
                #    print("Failed to get card name" + img1Path)


            try:
                print(outFile)
                subprocess.run(["magick", img1Path, img2Path, "+append", outFile], capture_output=True, text=True)
                print("images merged succesfully")
                #os.remove(img1Path)
                #os.remove(img2Path)
            except:
                print("error merging images")
        else:
            pass



if __name__ == "__main__":
    main()
