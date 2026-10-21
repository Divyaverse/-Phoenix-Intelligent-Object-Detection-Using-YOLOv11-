from ultralytics import YOLO
import cv2

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "models", "yolo11n.pt")
VIDEO_PATH = os.path.join(BASE_DIR, "videos", "test2.mp4")
if not os.path.exists(VIDEO_PATH):
    VIDEO_PATH = os.path.join(BASE_DIR, "videos", "test 1.mp4")

print(f"Loading person detection model from: {MODEL_PATH}")
model = YOLO(MODEL_PATH)

print("Model loaded.")
print("Person class ID:", [k for k, v in model.names.items() if v == "person"])

print(f"Opening video from: {VIDEO_PATH}")
cap = cv2.VideoCapture(VIDEO_PATH)

if not cap.isOpened():
    raise RuntimeError(f"Could not open video at {VIDEO_PATH}")

print("Video opened successfully.")

for frame_id in range(10):
    success, frame = cap.read()

    if not success:
        print(f"Could not read frame {frame_id}")
        break

    results = model(frame, conf=0.30, verbose=False)

    print(f"\nFrame {frame_id}:")

    person_found = False

    for result in results:
        for box in result.boxes:
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])
            class_name = model.names[class_id]

            if class_name == "person":
                person_found = True
                bbox = box.xyxy[0].tolist()

                print(
                    f"  PERSON | "
                    f"confidence={confidence:.3f} | "
                    f"bbox={bbox}"
                )

    if not person_found:
        print("  No person detected")

cap.release()

print("\nPerson detection test completed.")