import cv2
import numpy as np
import os

# --- Configuration de base ---
width, height = 600, 600
save_path = "output_frame.jpg"


def nothing(x):
    pass


# Création de la fenêtre et des curseurs (Trackbars)
cv2.namedWindow("LED Simulation")
cv2.createTrackbar("Taille Tache", "LED Simulation", 100, 250, nothing)
cv2.createTrackbar("Intensite LED", "LED Simulation", 150, 255, nothing)
cv2.createTrackbar("Teinte (H)", "LED Simulation", 0, 179, nothing)
cv2.createTrackbar("Bruit", "LED Simulation", 20, 100, nothing)
cv2.createTrackbar("Halo Size", "LED Simulation", 50, 150, nothing)

print("Simulation lancée. Appuyez sur 'q' pour quitter.")

while True:
    # 1. Récupération des valeurs des curseurs
    tache_radius = cv2.getTrackbarPos("Taille Tache", "LED Simulation")
    intensite = cv2.getTrackbarPos("Intensite LED", "LED Simulation")
    hue = cv2.getTrackbarPos("Teinte (H)", "LED Simulation")
    bruit_level = cv2.getTrackbarPos("Bruit", "LED Simulation")
    halo_size = cv2.getTrackbarPos("Halo Size", "LED Simulation")

    # 2. Création du fond blanc avec bruit
    # On génère une image blanche
    frame = np.full((height, width, 3), 255, dtype=np.uint8)

    # Ajout du bruit granulaire (style ISO élevé)
    noise = np.random.randint(
        -bruit_level, bruit_level, (height, width, 3), dtype="int16"
    )
    frame = np.clip(frame.astype("int16") + noise, 0, 255).astype("uint8")

    # 3. Dessin de la tache noire centrale
    center = (width // 2, height // 2)
    cv2.circle(frame, center, tache_radius, (0, 0, 0), -1)
    # Floutage de la bordure de la tache pour plus de réalisme
    frame = cv2.GaussianBlur(frame, (15, 15), 0)

    # 4. Création de la LED avec Halo (Gradient)
    # On travaille en HSV pour gérer facilement la couleur (Teinte)
    led_layer = np.zeros((height, width, 3), dtype=np.uint8)

    # Dessin du Halo dégradé
    for r in range(halo_size, 0, -1):
        alpha = int(intensite * (1 - r / halo_size))
        color_hsv = np.uint8([[[hue, 200, alpha]]])
        color_bgr = cv2.cvtColor(color_hsv, cv2.COLOR_HSV2BGR)[0][0]
        cv2.circle(led_layer, center, r, color_bgr.tolist(), -1)

    # Coeur blanc de la LED (saturation du capteur)
    white_core_radius = max(1, int(halo_size * 0.15 * (intensite / 255)))
    cv2.circle(led_layer, center, white_core_radius, (255, 255, 255), -1)

    # 5. Fusion de la LED sur l'image (Additif)
    final_frame = cv2.add(frame, led_layer)

    # 6. Affichage et enregistrement
    cv2.imshow("LED Simulation", final_frame)
    cv2.imwrite(save_path, final_frame)  # Enregistre chaque frame en temps réel

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cv2.destroyAllWindows()
