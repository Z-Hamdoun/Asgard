from picamera2 import Picamera2
from flask import Flask, Response
import cv2
import os
import sys

# Garde tes imports spécifiques si ton dossier pnp est au même endroit
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "pnp"))
from algo import PnPLandingSystem

import numpy as np


app = Flask(__name__)
picam2 = Picamera2()

picam2.configure(picam2.create_video_configuration(main={"size": (1280, 720)}))
picam2.start()


def generate_frames():
    detector = PnPLandingSystem()
    while True:
        frame_raw = picam2.capture_array()
        frame = cv2.cvtColor(frame_raw, cv2.COLOR_RGB2BGR)

        # Clone la frame originale pour dessiner dessus sans modifier la source
        output_frame = frame.copy()

        # Appel de la fonction de détection
        taches = detector.get_contours(frame)

        # --- Affichage des résultats ---
        for tache in taches:
            # 1. Dessiner le contour (en VERT, épaisseur 2)
            cv2.drawContours(output_frame, [tache["contours"]], -1, (0, 255, 0), 2)

            # 2. Dessiner le centre (point ROUGE plein)
            if tache["center"] is not None:
                cv2.circle(output_frame, tache["center"], 5, (0, 0, 255), -1)

                # Optionnel: Afficher les coordonnées du centre
                # cv2.putText(output_frame, f"({tache['center'][0]},{tache['center'][1]})",
                #             (tache['center'][0] + 10, tache['center'][1]),
                #             cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

            # 3. Dessiner le rectangle englobant (en BLEU, épaisseur 2)
            # On utilise directement les données de 'limits'
            lim = tache["limits"]
            cv2.rectangle(
                output_frame,
                (lim["x_min"], lim["y_min"]),
                (lim["x_max"], lim["y_max"]),
                (255, 0, 0),
                2,
            )

        ret, buffer = cv2.imencode(".jpg", output_frame)
        if not ret:
            continue

        frame_bytes = buffer.tobytes()

        yield (
            b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
        )


@app.route("/video")
def video():
    return Response(
        generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
