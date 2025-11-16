import cv2
import numpy as np
import requests

# URL of Raspberry Pi MJPEG stream
URL = "http://10.42.0.39:5000/video"   # ← replace 10.42.0.39 with Pi’s IP

# Open the HTTP MJPEG stream
stream = requests.get(URL, stream=True)
bytes_buffer = b""

print("Connected to stream. Press 'q' to quit.")

for chunk in stream.iter_content(chunk_size=1024):
    bytes_buffer += chunk
    a = bytes_buffer.find(b'\xff\xd8')   # JPEG start
    b = bytes_buffer.find(b'\xff\xd9')   # JPEG end

    if a != -1 and b != -1:
        jpg = bytes_buffer[a:b+2]
        bytes_buffer = bytes_buffer[b+2:]

        # Decode JPEG → frame
        frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)

        # ---- Convert BGR → HSV ----
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Threshold for magenta
        lower_magenta = np.array([140, 100, 150])
        upper_magenta = np.array([165, 255, 255])
        mask = cv2.inRange(hsv, lower_magenta, upper_magenta)

        mask = cv2.medianBlur(mask, 5)

        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Draw detection
        for c in contours:
            area = cv2.contourArea(c)
            if area > 50:
                (x, y), radius = cv2.minEnclosingCircle(c)
                center = (int(x), int(y))
                radius = int(radius)
                cv2.circle(frame, center, radius, (255, 255, 255), 2)
                cv2.circle(frame, center, 2, (0, 255, 0), -1)

        # Show output
        cv2.imshow("Camera (from Pi)", frame)
        cv2.imshow("Magenta Mask", mask)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

cv2.destroyAllWindows()