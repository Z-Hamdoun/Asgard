#!/usr/bin/env python3
"""
Programme principal pour tester la détection avec la webcam.
C'est ce fichier qu'on lance. Il s'occupe de filmer et d'afficher les résultats à l'écran.
"""

import cv2
import sys
import os
import numpy as np

# On dit à Python où trouver notre fichier "algo.py" (le cerveau)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "pnp"))
from algo import PnPLandingSystem


def draw_detected_points(frame, pnp_system):
    """
    Identifie et dessine les points blancs/bleus basés sur la luminosité.
    """
    # 1. Conversion en niveaux de gris (pour la luminosité)
    blue_channel = frame[:, :, 0]
    blurred = cv2.GaussianBlur(blue_channel, (7, 7), 0)

    # 2. Seuillage : on cherche les zones très claires (Blanc/Bleu ciel)
    # On utilise la valeur pnp_system.lower_val définie dans algo.py
    _, mask = cv2.threshold(blurred, pnp_system.lower_val, 255, cv2.THRESH_BINARY)

    # 3. Nettoyage morphologique
    mask = cv2.erode(mask, None, iterations=2)
    mask = cv2.dilate(mask, None, iterations=2)

    # 4. Recherche des contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    valid_contours = []
    for c in contours:
        area = cv2.contourArea(c)
        if pnp_system.max_contour_area > area > pnp_system.min_contour_area:
            # Calcul de circularité pour éviter de prendre des reflets allongés
            perimeter = cv2.arcLength(c, True)
            if perimeter == 0:
                continue
            circularity = 4 * np.pi * (area / (perimeter * perimeter))

            if circularity > 0.6:  # On garde ce qui est assez rond
                valid_contours.append(c)

    # On garde les 5 plus gros
    valid_contours = sorted(valid_contours, key=cv2.contourArea, reverse=True)[:5]

    points_2d = []
    for i, c in enumerate(valid_contours):
        M = cv2.moments(c)
        if M["m00"] != 0:
            cX = int(M["m10"] / M["m00"])
            cY = int(M["m01"] / M["m00"])
            points_2d.append([cX, cY])

            # Dessin : Jaune pour le centre, Cyan pour le contour
            cv2.circle(frame, (cX, cY), 7, (0, 255, 255), -1)
            cv2.putText(
                frame,
                str(i + 1),
                (cX + 10, cY - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 255),
                2,
            )

    return points_2d


def main():
    # 1. On allume le "cerveau" (notre algorithme)
    pnp_system = PnPLandingSystem(marker_distance=0.40, net_depth=0.20)

    # 2. On allume la webcam de l'ordinateur (la caméra 0 est généralement la principale)
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print(
            "❌ Erreur : Impossible d'allumer la webcam. Vérifiez qu'elle n'est pas utilisée ailleurs."
        )
        return

    print("✅ Webcam ouverte et prête !")
    print("\n📋 Commandes clavier pendant la vidéo :")
    print("  - [q] : Quitter le programme")
    print("  - [s] : Prendre une capture d'écran (photo)")
    print("  - [v] : Afficher/Cacher les textes techniques dans la console (Verbose)\n")

    verbose = True
    frame_count = 0

    # 3. BOUCLE VIDÉO : On lit l'image en continu, 30 fois par seconde
    # Dans test_camera_pnp.py (la boucle principale)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.resize(frame, (1280, 720))

        # On appelle l'algo UNE SEULE FOIS
        # Il nous donne la distance ET les points qu'il a réellement calculés
        result, pts = pnp_system.get_landing_vector(frame, verbose=verbose)

        # DESSIN : On dessine les points récupérés de l'algo
        for i, p in enumerate(pts):
            cv2.circle(frame, (p[0], p[1]), 8, (255, 0, 0), -1)  # Bleu pour le dessin
            cv2.putText(
                frame,
                str(i + 1),
                (p[0] + 10, p[1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 0, 0),
                2,
            )

        if result:
            dx, dy, dz = result
            status = f"LOCK: X={dx:.2f} Y={dy:.2f} Z={dz:.2f}"
            color = (0, 255, 0)
        else:
            status = "RECHERCHE..."
            color = (0, 0, 255)

        cv2.putText(frame, status, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
        cv2.imshow("Test PNP Bleu", frame)
        # 4. GESTION DU CLAVIER
        key = cv2.waitKey(1) & 0xFF  # On lit la touche appuyée

        if key == ord("q"):  # Si on appuie sur 'q'
            print("\n👋 Fermeture du programme...")
            break
        elif key == ord("s"):  # Si on appuie sur 's'
            filename = f"photo_test_{frame_count}.png"
            cv2.imwrite(filename, frame)
            print(f"📸 Clic ! Photo sauvegardée sous le nom: {filename}")
        elif key == ord("v"):  # Si on appuie sur 'v'
            verbose = not verbose
            print(f"🔊 Textes de debug: {'ACTIVÉS' if verbose else 'DÉSACTIVÉS'}")

    # Quand on sort de la boucle (après avoir appuyé sur 'q'), on éteint proprement la caméra
    cap.release()
    cv2.destroyAllWindows()  # On ferme la fenêtre vidéo
    print("✅ Programme terminé")


if __name__ == "__main__":
    main()
