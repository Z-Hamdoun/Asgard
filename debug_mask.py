import cv2
from picamera2 import Picamera2
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "pnp"))
from algo import PnPLandingSystem


def main():
    picam2 = Picamera2()
    config = picam2.create_video_configuration(
        main={"size": (1280, 720), "format": "BGR888"}
    )
    picam2.configure(config)
    picam2.start()

    pnp = PnPLandingSystem()

    print("Lancement du mode Mixte (Contours + Points)...")

    try:
        while True:
            frame_raw = picam2.capture_array()
            frame = cv2.cvtColor(frame_raw, cv2.COLOR_RGB2BGR)

            # On récupère les résultats + les deux masques
            contours, m_dark, m_bright = pnp.get_contours(frame)

            for coords, area, cnt_large, cnt_small in contours:
                # Dessins sur la frame principale
                cv2.drawContours(frame, [cnt_large], -1, (0, 0, 255), 2)
                cv2.drawContours(frame, [cnt_small], -1, (0, 255, 0), 2)
                cv2.circle(frame, coords, 5, (255, 0, 0), -1)
                cv2.putText(
                    frame,
                    str(int(area)),
                    (coords[0] + 10, coords[1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 0, 0),
                    2,
                )

            # 1. Fenêtre principale
            cv2.imshow("RPi - Detection Mixte", frame)
            cv2.namedWindow("RPi - Detection Mixte")
            cv2.moveWindow("RPi - Detection Mixte", 0, 0)

            # 2. Fenêtre Masque Sombre (Grosse tache)
            cv2.imshow("Masque 1 - Sombre", m_dark)
            cv2.namedWindow("Masque 1 - Sombre")
            cv2.moveWindow("Masque 1 - Sombre", 650, 0)  # Décale à droite

            # 3. Fenêtre Masque Clair (Petite tache / LED)
            cv2.imshow("Masque 2 - Clair", m_bright)
            cv2.namedWindow("Masque 2 - Clair")

            cv2.moveWindow("Masque 2 - Clair", 650, 400)  # Décale en bas à droite
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        picam2.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
