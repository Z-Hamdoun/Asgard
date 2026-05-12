import os
import cv2
import numpy as np
from picamera2 import Picamera2

# ==========================================================
# CONFIGURATION
# ==========================================================
CHESSBOARD_SIZE = (9, 6)
SAVE_DIR = "images_calib"
MAX_PHOTOS = 30

# Résolution basse MAIS full FOV
WIDTH = 640
HEIGHT = 360

# Full sensor PiCam 3 Wide
SENSOR_WIDTH = 4608
SENSOR_HEIGHT = 2592

# ==========================================================
# DOSSIER
# ==========================================================
os.makedirs(SAVE_DIR, exist_ok=True)

# ==========================================================
# CAMERA INIT
# ==========================================================
print("[INFO] Initialisation PiCamera 3 Wide...")

picam2 = Picamera2()

# IMPORTANT :
# low resolution + hardware downscale
# while keeping FULL SENSOR FOV
config = picam2.create_video_configuration(
    main={
        "size": (WIDTH, HEIGHT),
        "format": "RGB888"
    },
    controls={
        "FrameRate": 60
    },
    buffer_count=4
)

picam2.configure(config)

# ==========================================================
# FORCE FULL SENSOR FOV
# ==========================================================
picam2.start()

picam2.set_controls({
    "ScalerCrop": (0, 0, SENSOR_WIDTH, SENSOR_HEIGHT),
    "AeEnable": True,
    "ExposureValue": 0
})

print("\n" + "="*55)
print("📸 CALIBRATION PiCamera 3 Wide - FULL FOV MODE")
print("="*55)
print("Résolution :", WIDTH, "x", HEIGHT)
print("FOV : MAXIMUM (~120°)")
print("FPS cible : 60")
print()
print("[ESPACE] -> sauvegarder")
print("[Q]       -> quitter")
print("="*55 + "\n")

photos_taken = 0

try:

    while photos_taken < MAX_PHOTOS:

        # Capture
        frame = picam2.capture_array()

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        display = frame.copy()

        # Better chessboard detection for fisheye
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

            # Corner refinement
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
                "DAMIER DETECTE - ESPACE",
                (15, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2
            )

        else:

            cv2.putText(
                display,
                "RECHERCHE DU DAMIER...",
                (15, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2
            )

        cv2.putText(
            display,
            f"Photos : {photos_taken}/{MAX_PHOTOS}",
            (15, HEIGHT - 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

        cv2.imshow("Calibration PiCam3 Wide FULL FOV", display)

        key = cv2.waitKey(1) & 0xFF

        # ==================================================
        # SAVE IMAGE
        # ==================================================
        if key == ord(' '):

            if ret:

                filepath = os.path.join(
                    SAVE_DIR,
                    f"calib_{photos_taken+1:02d}.png"
                )

                # Save RAW frame (without drawings)
                cv2.imwrite(filepath, frame)

                photos_taken += 1

                print(f"✅ Photo {photos_taken}/{MAX_PHOTOS} sauvegardée")

                # White flash
                flash = np.ones_like(display) * 255

                cv2.imshow(
                    "Calibration PiCam3 Wide FULL FOV",
                    flash
                )

                cv2.waitKey(100)

            else:
                print("⚠️ Damier non détecté")

        # ==================================================
        # QUIT
        # ==================================================
        elif key == ord('q'):

            print("\n[INFO] Arrêt demandé")
            break

except KeyboardInterrupt:

    print("\n[INFO] Interruption clavier")

finally:

    picam2.stop()
    picam2.close()

    cv2.destroyAllWindows()

    print("\n[INFO] Capture terminée")