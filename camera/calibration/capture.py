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

# ==========================================================
# INIT DOSSIER
# ==========================================================
os.makedirs(SAVE_DIR, exist_ok=True)

# ==========================================================
# CAMERA INIT
# ==========================================================
picam2 = Picamera2()

# IMPORTANT :
# use full sensor mode to maximize FOV
config = picam2.create_preview_configuration(
    main={
        "size": (2304, 1296),   # Full wide mode
        "format": "RGB888"
    },
    buffer_count=4
)

picam2.configure(config)

# Disable digital crop
picam2.set_controls({
    "ScalerCrop": (0, 0, 4608, 2592),
    "FrameRate": 30,
    "AeEnable": True
})

picam2.start()

print("\n======================================")
print(" PiCamera 3 Wide Calibration Capture ")
print("======================================")
print("SPACE -> save image")
print("Q     -> quit")
print("======================================\n")

photos_taken = 0

try:

    while photos_taken < MAX_PHOTOS:

        frame = picam2.capture_array()

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        display = frame.copy()

        # Better detection for fisheye lenses
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

            # Refine corners
            criteria = (
                cv2.TERM_CRITERIA_EPS +
                cv2.TERM_CRITERIA_MAX_ITER,
                30,
                0.001
            )

            corners2 = cv2.cornerSubPix(
                gray,
                corners,
                (11, 11),
                (-1, -1),
                criteria
            )

            cv2.drawChessboardCorners(
                display,
                CHESSBOARD_SIZE,
                corners2,
                ret
            )

            cv2.putText(
                display,
                "DAMIER DETECTE - SPACE",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2
            )

        else:

            cv2.putText(
                display,
                "RECHERCHE DU DAMIER",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 0, 255),
                2
            )

        cv2.putText(
            display,
            f"{photos_taken}/{MAX_PHOTOS}",
            (20, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            2
        )

        cv2.imshow("Calibration PiCam3 Wide", display)

        key = cv2.waitKey(1) & 0xFF

        # SAVE
        if key == ord(" "):

            if ret:

                filename = os.path.join(
                    SAVE_DIR,
                    f"calib_{photos_taken:02d}.png"
                )

                cv2.imwrite(filename, frame)

                photos_taken += 1

                print(f"[OK] Saved {filename}")

                flash = np.ones_like(display) * 255
                cv2.imshow("Calibration PiCam3 Wide", flash)
                cv2.waitKey(100)

            else:
                print("[WARN] Damier non détecté")

        # QUIT
        elif key == ord("q"):
            break

finally:

    picam2.stop()
    picam2.close()
    cv2.destroyAllWindows()

    print("\nCapture terminée.")