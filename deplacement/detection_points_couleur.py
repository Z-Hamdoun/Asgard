# Detect bright magenta dots from Raspberry Pi camera in real-time
# Requires: sudo apt install python3-picamera2 python3-opencv

from picamera2 import Picamera2
import cv2
import numpy as np

# --- Camera setup ---
picam2 = Picamera2()
config = picam2.create_preview_configuration(
    main={"size": (640, 480), "format": "RGB888"}  # directly get RGB frames
)
picam2.configure(config)
picam2.start()

print("Press 'q' to quit.")

while True:
    # Capture frame directly into an RGB numpy array
    frame = picam2.capture_array()

    # Convert RGB → HSV color space
    hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)

    # --- Threshold for bright magenta color ---
    # Magenta ≈ 140–165° hue (in OpenCV scale: 140–165)
    # S and V thresholds exclude dull or dark pixels
    lower_magenta = np.array([140, 100, 150])
    upper_magenta = np.array([165, 255, 255])
    mask = cv2.inRange(hsv, lower_magenta, upper_magenta)

    # Optional: noise cleanup
    mask = cv2.medianBlur(mask, 5)

    # Find contours of detected blobs
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Draw contours and centers on original frame
    for c in contours:
        area = cv2.contourArea(c)
        if area > 50:  # filter out small noise
            (x, y), radius = cv2.minEnclosingCircle(c)
            center = (int(x), int(y))
            radius = int(radius)
            cv2.circle(frame, center, radius, (255, 255, 255), 2)
            cv2.circle(frame, center, 2, (0, 255, 0), -1)

    # Show the images
    cv2.imshow("Camera (RGB)", cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
    cv2.imshow("Magenta mask", mask)

    # Exit on 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Cleanup
cv2.destroyAllWindows()
picam2.stop()