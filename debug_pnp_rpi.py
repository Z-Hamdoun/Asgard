import time

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

picam2.configure(picam2.create_video_configuration(main={"size": (848, 480)}))
picam2.start()


def generate_frames():
    detector = PnPLandingSystem()
    while True:
        frame_raw = picam2.capture_array()
        frame = cv2.cvtColor(frame_raw, cv2.COLOR_RGB2BGR)

        # On récupère les contours ET le masque (thresh)
        vector, get_contours = detector.get_landing_vector(frame)
        taches1, taches2, taches3, thresh = get_contours

        # OPTION A : Afficher UNIQUEMENT le masque noir et blanc
        output_frame = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)

        # OPTION B : Afficher les contours colorés SUR le masque (plus pratique pour debug)
        # Comme 'thresh' est en niveaux de gris, on le repasse en BGR pour voir les couleurs
        # output_frame = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)

        for i in range(len(taches1)):
            # On dessine en VERT sur le masque pour voir si la détection matche le seuil
            cv2.drawContours(output_frame, [taches1[i]["contours"]], -1, (0, 255, 0), 2)
            cv2.drawContours(output_frame, [taches2[i]["contours"]], -1, (0, 225, 0), 2)
            cv2.drawContours(output_frame, [taches3[i]["contours"]], -1, (0, 205, 0), 2)
            if taches3[i]["center"] is not None:
                cX, cY = taches3[i]["center"]
                cv2.circle(output_frame, (cX, cY), 5, (0, 0, 255), -1)
                aire = taches3[i]["area"]
                texte_aire = f"A: {int(aire)}:{int(taches1[i]["area"])}"

                perimeter = cv2.arcLength(taches3[i]["contours"], True)
                if perimeter == 0:
                    return False
                circularity = 4 * np.pi * (aire / (perimeter**2))
                # 3. Afficher l'aire juste au-dessus de la tache
                # On décale un peu le texte (-15 pixels en Y) pour ne pas chevaucher le centre
                cv2.putText(
                    output_frame,
                    texte_aire + "circ: " + str(circularity),
                    (cX - 20, cY - 15),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,  # Taille plus petite pour ne pas encombrer l'image
                    (255, 255, 255),  # Blanc pour la lisibilité
                    1,
                    cv2.LINE_AA,
                )
        nb_taches = len(taches1)
        texte = f"Taches detectees: {nb_taches}"
        vector_text = "no vector"
        if vector is not None:
            vector_text = (
                "x:"
                + str(round(vector[0], 2))
                + " y:"
                + str(round(vector[1], 2))
                + " z:"
                + str(round(vector[2], 2))
            )
        # 2. Choisir la couleur (Vert si on en a 5, Rouge sinon)
        couleur_texte = (0, 255, 0) if nb_taches == 5 else (0, 0, 255)

        # 3. Dessiner le texte sur l'image
        cv2.putText(
            output_frame,
            texte,
            (20, 40),  # Position (x, y) en pixels depuis le coin haut-gauche
            cv2.FONT_HERSHEY_SIMPLEX,  # Police de caractères
            0.8,  # Taille de la police
            couleur_texte,  # Couleur (BGR)
            2,  # Épaisseur du trait
            cv2.LINE_AA,  # Antialiasing pour un texte plus lisse
        )
        cv2.putText(
            output_frame,
            vector_text,
            (20, 80),  # Position (x, y) en pixels depuis le coin haut-gauche
            cv2.FONT_HERSHEY_SIMPLEX,  # Police de caractères
            0.8,  # Taille de la police
            couleur_texte,  # Couleur (BGR)
            2,  # Épaisseur du trait
            cv2.LINE_AA,  # Antialiasing pour un texte plus lisse
        )
        # Encodage et envoi
        ret, buffer = cv2.imencode(".jpg", output_frame)
        if not ret:
            continue
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
        )


@app.route("/video")
def video():
    return Response(
        generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
