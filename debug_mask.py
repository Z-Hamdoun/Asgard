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
            frame = picam2.capture_array()

            # Appel de l'algo modifié
            contours = pnp.get_contours(frame)
            for c in contours:
                print(cv2.contourArea(c))
            result, centers = pnp.get_landing_vector(frame)

            # 1. DESSIN DES CONTOURS (comme dans debug_mask)
            # On dessine la silhouette de ce qui a été détecté en Jaune
            cv2.drawContours(frame, contours, -1, (0, 255, 255), 2)

            # 2. DESSIN DES POINTS CENTRAUX (comme dans test_camera)
            for i, p in enumerate(centers):
                # Un point bleu plein au centre
                cv2.circle(frame, (p[0], p[1]), 5, (255, 0, 0), -1)
                cv2.putText(
                    frame,
                    str(i + 1),
                    (p[0] + 10, p[1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 0, 0),
                    2,
                )

            # 3. AFFICHAGE DES INFOS PNP
            if result:
                dx, dy, dz = result
                cv2.putText(frame, f"Z: {dz:.2f}m", (20, 50), 0, 1, (0, 255, 0), 2)
            else:
                cv2.putText(
                    frame, f"Points: {len(centers)}/5", (20, 50), 0, 1, (0, 0, 255), 2
                )

            cv2.imshow("RPi - Detection Mixte", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        picam2.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
