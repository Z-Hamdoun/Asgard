import os
import cv2
import numpy as np
from picamera2 import Picamera2

# ==========================================================
# CONFIG
# ==========================================================
CHESSBOARD_SIZE = (9, 6)

SAVE_DIR = "images_calib"
MAX_PHOTOS = 30

WIDTH = 848
HEIGHT = 480

os.makedirs(SAVE_DIR, exist_ok=True)

# ==========================================================
# CAMERA
# ==========================================================
picam2 = Picamera2()

# FORCE FULL SENSOR MODE
video_config = picam2.create_video_configuration(

    sensor={
        "output_size": (4608, 2592),
        "bit_depth": 10
    },

    main={
        "size": (WIDTH, HEIGHT),
        "format": "RGB888"
    },

    controls={
        "FrameRate": 60
    },

    buffer_count=6
)

picam2.configure(video_config)

picam2.start()

# FORCE FULL SENSOR CROP
picam2.set_controls({
    "ScalerCrop": (0, 0, 4608, 2592)
})

print("\n========================================")
print(" PiCam3 Wide FULL FOV Calibration ")
print("========================================")
print("SPACE -> save")
print("Q     -> quit")
print("========================================\n")

photos_taken = 0

try:

    while True:

        frame = picam2.capture_array()

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        display = frame.copy()

        flags = (
            cv2.CALIB_CB_ADAPTIVE_THRESH
            + cv2.CALIB_CB_NORMALIZE_IMAGE
            + cv2.CALIB_CB_FAST_CHECK
        )

        ret, corners = cv2.findChessboardCorners(
            gray,
            CHESSBOARD_SIZE,
            flags
        )

        if ret:

            cv2.drawChessboardCorners(
                display,
                CHESSBOARD_SIZE,
                corners,
                ret
            )

            cv2.putText(
                display,
                "DETECTED - SPACE",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2
            )

        else:

            cv2.putText(
                display,
                "SEARCHING...",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2
            )

        cv2.putText(
            display,
            f"{photos_taken}/{MAX_PHOTOS}",
            (20, HEIGHT - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

        cv2.imshow("FULL FOV", display)

        key = cv2.waitKey(1) & 0xFF

        if key == ord(' '):

            if ret:

                filename = os.path.join(
                    SAVE_DIR,
                    f"calib_{photos_taken:02d}.png"
                )

                cv2.imwrite(filename, frame)

                photos_taken += 1

                print("[OK]", filename)

        elif key == ord('q'):
            break

finally:

    picam2.stop()
    picam2.close()

    cv2.destroyAllWindows()