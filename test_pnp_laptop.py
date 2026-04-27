import cv2
import os
import sys

# Garde tes imports spécifiques si ton dossier pnp est au même endroit
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "pnp"))
from algo import PnPLandingSystem

import numpy as np


def main():
    # Initialisation de la caméra (0 est généralement la webcam par défaut)
    cap = cv2.VideoCapture(0)

    # Vérification
    if not cap.isOpened():
        print("Erreur: Impossible d'ouvrir la caméra.")
        return

    detector = PnPLandingSystem()
    print("Test lancé. Appuyez sur 'q' pour quitter.")

    while True:
        # Capture trame par trame
        ret, frame = cap.read()
        if not ret:
            print("Erreur de capture.")
            break

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

        # Affichage de la fenêtre
        cv2.imshow("Detection de Taches - Test", output_frame)

        # Quitter si on appuie sur 'q'
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    # Nettoyage
    cap.release()
    cv2.destroyAllWindows()
    print("Test terminé.")


if __name__ == "__main__":
    main()
