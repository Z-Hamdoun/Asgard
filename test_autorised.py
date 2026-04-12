import cv2
import numpy as np
from tqdm import tqdm  # Pour la barre de progression (recommandé !)


def print_authorised():
    # --- Définition des plages HSV (identiques à ton code principal) ---

    # Grosse tache : du noir au bleu "moyen"
    # Note : Le noir est inclus car la "Value" (luminosité) va de 0 à 150.
    # Un noir pur est [0, 0, 0], donc il passe le filtre Value < 150.
    lower_dark = np.array([140, 50, 0])  # Bleu marine / Noir
    upper_dark = np.array([190, 255, 150])  # Bleu moyen, luminosité plafonnée
    lower_bright = np.array([130, 0, 190])  # Bleu clair / Désaturé
    upper_bright = np.array([180, 255, 255])  # Blanc / Bleu très vif

    # --- Préparation des images ---
    # Nous allons créer des images où l'axe X est la Saturation,
    # l'axe Y est la Valeur (luminosité), et nous itérerons sur la Teinte (Hue).
    # Cela permet de voir toutes les couleurs "autorisées" pour chaque Teinte.

    img_dark_result = np.zeros((256, 256, 3), dtype=np.uint8)
    img_bright_result = np.zeros((256, 256, 3), dtype=np.uint8)

    print("Génération des dégradés autorisés (ceci peut prendre quelques secondes)...")

    # --- Itération à travers tout l'espace HSV autorisé ---
    # Nous ne testons que les teintes (Hue) couvertes par les masques
    # pour gagner du temps.

    # On couvre la plage de teinte combinée (80 à 140)
    h_min = min(lower_dark[0], lower_bright[0])
    h_max = max(upper_dark[0], upper_bright[0])

    # Utilisation de tqdm pour afficher une barre de progression si installée
    # Sinon, une boucle standard : for h in range(h_min, h_max + 1):
    try:
        hue_range = tqdm(range(h_min, h_max + 1), desc="Teintes")
    except ImportError:
        print(
            "Installation de 'tqdm' recommandée ('pip install tqdm') pour la progression."
        )
        hue_range = range(h_min, h_max + 1)

    for h in hue_range:
        for s in range(256):  # Saturation
            for v in range(256):  # Value (Luminosité)

                hsv_pixel = np.array([[[h, s, v]]], dtype=np.uint8)

                # Vérifier pour le masque SOMBRES
                if (
                    h >= lower_dark[0]
                    and h <= upper_dark[0]
                    and s >= lower_dark[1]
                    and s <= upper_dark[1]
                    and v >= lower_dark[2]
                    and v <= upper_dark[2]
                ):
                    # Convertir en BGR pour l'affichage dans l'image résultante
                    bgr_pixel = cv2.cvtColor(hsv_pixel, cv2.COLOR_HSV2BGR)[0][0]
                    img_dark_result[v, s] = bgr_pixel

                # Vérifier pour le masque CLAIRS
                if (
                    h >= lower_bright[0]
                    and h <= upper_bright[0]
                    and s >= lower_bright[1]
                    and s <= upper_bright[1]
                    and v >= lower_bright[2]
                    and v <= upper_bright[2]
                ):
                    # Convertir en BGR
                    bgr_pixel = cv2.cvtColor(hsv_pixel, cv2.COLOR_HSV2BGR)[0][0]
                    img_bright_result[v, s] = bgr_pixel

    # --- Légendes sur les images ---
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(
        img_dark_result,
        "Masque Sombre (Externe)",
        (10, 20),
        font,
        0.5,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        img_bright_result,
        "Masque Clair (Interne)",
        (10, 20),
        font,
        0.5,
        (0, 0, 0),
        1,
        cv2.LINE_AA,
    )

    print("Génération terminée. Sauvegarde des images.")
    # Sauvegarde des images
    cv2.imwrite("autorised_dark.png", img_dark_result)
    cv2.imwrite("autorised_bright.png", img_bright_result)

    # Optionnel : Afficher les images si un environnement graphique est disponible
    # cv2.imshow('Autorised Dark', img_dark_result)
    # cv2.imshow('Autorised Bright', img_bright_result)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()


if __name__ == "__main__":
    print_authorised()
