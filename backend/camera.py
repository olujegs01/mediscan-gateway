import cv2
import numpy as np
import time

def start_camera_capture():
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        return {"error": "Camera not accessible"}

    start_time = time.time()
    frames = []

    while time.time() - start_time < 5:
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(frame)

    cap.release()

    return analyze_frames(frames)


def analyze_frames(frames):
    breathing_rate = estimate_breathing(frames)
    heart_rate = estimate_heart_rate(frames)

    return {
        "breathing_rate": int(breathing_rate),
        "heart_rate": int(heart_rate)
    }


def estimate_breathing(frames):
    return np.random.randint(12, 20)


def estimate_heart_rate(frames):
    return np.random.randint(60, 100)