from PIL import Image
from pytesseract import pytesseract
from ultralytics import YOLO
import cv2
import numpy as np
import time
import os

findCardModel = YOLO("findCard.pt")


def main():
    print("Hello from pokemon-card-merger!")


if __name__ == "__main__":
    main()
