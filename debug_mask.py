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
        # Dans la boucle principale de ton script de debug
        while True:
            frame_raw = picam2.capture_array()

            # INVERSION ICI : On passe de RGB à BGR pour que OpenCV soit content
            frame = cv2.cvtColor(frame_raw, cv2.COLOR_RGB2BGR)

            # Appel de l'algo modifié
            contours = pnp.get_contours(frame)
            for coords, area in contours:
                print(area)
                cv2.putText(
                    frame,
                    str(area),
                    (coords[0] + 10, coords[1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 0, 0),
                    2,
                )
                cv2.circle(frame, (coords[0], coords[1]), 5, (255, 0, 0), -1)

            # # 3. AFFICHAGE DES INFOS PNP
            # if result:
            #     dx, dy, dz = result
            #     cv2.putText(frame, f"Z: {dz:.2f}m", (20, 50), 0, 1, (0, 255, 0), 2)
            # else:
            #     cv2.putText(
            #         frame, f"Points: {len(centers)}/5", (20, 50), 0, 1, (0, 0, 255), 2
            #     )

            cv2.imshow("RPi - Detection Mixte", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        picam2.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
