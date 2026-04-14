import cv2
import os
import sys

# Garde tes imports spécifiques si ton dossier pnp est au même endroit
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "pnp"))
from algo import PnPLandingSystem

import numpy as np


def nothing(x):
    pass


def main():
    # cap = cv2.VideoCapture(0) # Inutile maintenant
    path_image = "output_frame.jpg"
    pnp = PnPLandingSystem()

    print("Lecture continue de l'image. Appuyez sur 'q' pour quitter.")

    try:
        while True:
            # ON LIT L'IMAGE À CHAQUE TOUR DE BOUCLE
            frame = cv2.imread(path_image)

            # Sécurité : si l'image est vide ou en cours d'écriture par un autre script
            if frame is None:
                cv2.waitKey(
                    10
                )  # Petite pause pour laisser le temps au fichier de se créer
                continue

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

            # --- AFFICHAGE DES VALEURS SUR LES MASQUES ---
            # Pour t'aider, on écrit les valeurs sur les fenêtres de masque
            cv2.putText(
                m_dark,
                f"H:{pnp.h_min_d}-{pnp.h_max_d} Smin:{pnp.s_min_d} Vmax:{pnp.v_max_d}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                255,
                2,
            )

            cv2.putText(
                m_bright,
                f"H:{pnp.h_min_b}-{pnp.h_max_b} Smin:{pnp.s_min_b} Vmin:{pnp.v_min_b}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                255,
                2,
            )
            if m_dark is not None:
                m_dark_color = cv2.cvtColor(m_dark, cv2.COLOR_GRAY2BGR)
                m_bright_color = cv2.cvtColor(m_bright, cv2.COLOR_GRAY2BGR)

                # 2. Fenêtre Masque Sombre (Grosse tache)
                print(contours)
                for coords, area, cnt_large, cnt_small in contours:
                    # On dessine sur m_dark_color (qui accepte le rouge et le vert maintenant)
                    cv2.drawContours(m_dark_color, [cnt_large], -1, (0, 0, 255), 2)
                    cv2.drawContours(m_dark_color, [cnt_small], -1, (0, 255, 0), 2)

                cv2.imshow("Masque 1 - Sombre", m_dark_color)
                # ... tes fonctions namedWindow/resizeWindow/moveWindow ...

                # 3. Fenêtre Masque Clair (Petite tache / LED)
                for coords, area, cnt_large, cnt_small in contours:
                    # On dessine sur m_bright_color
                    cv2.drawContours(m_bright_color, [cnt_large], -1, (0, 0, 255), 2)
                    cv2.drawContours(m_bright_color, [cnt_small], -1, (0, 255, 0), 2)

                cv2.imshow("Masque 2 - Clair", m_bright_color)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        # cap.release() # N'est plus nécessaire pour une image
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
