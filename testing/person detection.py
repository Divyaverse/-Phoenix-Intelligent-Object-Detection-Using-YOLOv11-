from ultralytics import YOLO
import cv2

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "models", "yolo11n.pt")
VIDEO_PATH = os.path.join(BASE_DIR, "videos", "test2.mp4")
if not os.path.exists(VIDEO_PATH):
    VIDEO_PATH = os.path.join(BASE_DIR, "videos", "test 1.mp4")

model = YOLO(MODEL_PATH)

cap = cv2.VideoCapture(VIDEO_PATH)

if not cap.isOpened():
    raise RuntimeError(f"Could not open test video at {VIDEO_PATH}")

for i in range(10):
    success, frame = cap.read()

    if not success:
        print("Could not read frame", i)
        break

    results = model(frame, conf=0.30, verbose=False)

    print(f"\nFrame {i}")

    for result in results:
        for box in result.boxes:
            cls_id = int(box.cls[0])
            confidence = float(box.conf[0])
            class_name = model.names[cls_id]

            if class_name == "person":
                print(
                    f"PERSON detected | "
                    f"confidence={confidence:.3f} | "
                    f"bbox={box.xyxy[0].tolist()}"
                )

cap.release() 