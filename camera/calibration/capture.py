import os
import time
import cv2
import numpy as np
from picamera2 import Picamera2

# ==========================================================
# CONFIGURATION (Doit être identique à calibrate_camera.py)
# ==========================================================
CHESSBOARD_SIZE = (9, 6) # Intersections intérieures (Colonnes, Lignes)
SAVE_DIR = "images_calib"
MAX_PHOTOS = 20          # Nombre de photos à prendre au total

def main():
    # 1. Création du dossier s'il n'existe pas
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)
        print(f"[INFO] Dossier {SAVE_DIR}/ créé.")

    # 2. Initialisation de la Caméra (Résolution cible: 640x480)
    print("[INFO] Démarrage de la caméra...")
    picam2 = Picamera2()
    picam2.preview_configuration.main.size = (640, 480)
    picam2.preview_configuration.main.format = "RGB888"
    picam2.preview_configuration.controls.FrameRate = 30
    picam2.configure("preview")
    picam2.start()
    picam2.set_controls({"AeEnable": True, "ExposureValue": 0})
    time.sleep(2) # Temps de chauffe

    print("\n" + "="*50)
    print("🤖 ASSISTANT DE CALIBRATION AUTOMATIQUE")
    print("="*50)
    print(f"1. Placez votre damier ({CHESSBOARD_SIZE[0]}x{CHESSBOARD_SIZE[1]}) devant la caméra.")
    print(f"2. Bougez-le doucement, inclinez-le (haut, bas, gauche, droite).")
    print(f"3. Le script prendra automatiquement une photo dès qu'il le verra !")
    print("-> Appuyez sur Ctrl+C pour quitter à tout moment.\n")

    photos_taken = 0
    cooldown_time = 0

    try:
        while photos_taken < MAX_PHOTOS:
            # Capture de l'image
            frame_rgb = picam2.capture_array()
            frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

            # Si on n'est pas en période de pause
            if time.time() > cooldown_time:
                
                # Affiche un petit message de statut qui se met à jour sur la même ligne
                print(f"⏳ Recherche du damier... ({photos_taken}/{MAX_PHOTOS})", end="\r")

                # L'IA cherche le damier dans l'image
                ret, _ = cv2.findChessboardCorners(gray, CHESSBOARD_SIZE, None)

                # Si le damier est trouvé de manière nette
                if ret:
                    # On sauvegarde l'image
                    filepath = os.path.join(SAVE_DIR, f"calib_{photos_taken+1:02d}.jpg")
                    cv2.imwrite(filepath, frame_bgr)
                    photos_taken += 1
                    
                    # On efface la ligne "Recherche..." et on affiche le succès
                    print(" " * 40, end="\r") 
                    print(f"✅ [{photos_taken}/{MAX_PHOTOS}] Damier détecté et photo sauvegardée !")
                    
                    if photos_taken < MAX_PHOTOS:
                        print("👉 Changez l'angle ou la position du damier... (Pause de 3 secondes)")
                        # Pause de 3 secondes pour éviter de prendre 10 fois la même position
                        cooldown_time = time.time() + 3.0

            # Petite pause pour ne pas saturer le CPU à 100%
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n\n[INFO] Capture interrompue par l'utilisateur.")
    
    finally:
        picam2.stop()
        picam2.close()
        print("\n" + "="*50)
        print(f"📸 TERMINÉ ! {photos_taken} photos ont été sauvegardées dans le dossier '{SAVE_DIR}/'.")
        print("Vous pouvez maintenant lancer le script de calcul :")
        print("python tools/calibrate_camera.py")
        print("="*50)

if __name__ == "__main__":
    main()