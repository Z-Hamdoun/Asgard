import os
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

    print("\n" + "="*50)
    print("📸 ASSISTANT DE CALIBRATION MANUEL (AVEC ÉCRAN)")
    print("="*50)
    print("-> La fenêtre vidéo va s'ouvrir.")
    print("-> APPUYEZ SUR [ESPACE] pour prendre une photo valide.")
    print("-> APPUYEZ SUR [Q] pour quitter le programme.")
    print("="*50 + "\n")

    photos_taken = 0

    try:
        while photos_taken < MAX_PHOTOS:
            # Capture de l'image
            frame_rgb = picam2.capture_array()
            frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            
            # Copie de l'image pour l'affichage (HUD)
            display_frame = frame_bgr.copy()

            # L'IA cherche le damier dans l'image en direct
            ret, corners = cv2.findChessboardCorners(gray, CHESSBOARD_SIZE, None)

            if ret:
                # Dessine le motif arc-en-ciel pour confirmer à l'utilisateur
                cv2.drawChessboardCorners(display_frame, CHESSBOARD_SIZE, corners, ret)
                cv2.putText(display_frame, "DAMIER DETECTE -> ESPACE POUR CAPTURER", (10, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            else:
                cv2.putText(display_frame, "RECHERCHE DU DAMIER...", (10, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

            # Affichage du compteur
            cv2.putText(display_frame, f"Photos : {photos_taken}/{MAX_PHOTOS}", (10, 460), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            # Affiche la vidéo sur l'écran HDMI
            cv2.imshow("Calibration Camera - Vue en direct", display_frame)

            # Gestion du clavier
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord(' '): # Touche ESPACE
                if ret:
                    # On sauvegarde l'image ORIGINALE (frame_bgr) sans les dessins !
                    filepath = os.path.join(SAVE_DIR, f"calib_{photos_taken+1:02d}.jpg")
                    cv2.imwrite(filepath, frame_bgr)
                    photos_taken += 1
                    print(f"✅ Photo {photos_taken}/{MAX_PHOTOS} sauvegardée !")
                    
                    # Petit flash d'écran blanc pour confirmer la capture
                    flash = np.ones_like(display_frame) * 255
                    cv2.imshow("Calibration Camera - Vue en direct", flash)
                    cv2.waitKey(100)
                else:
                    print("⚠️ Impossible de capturer : le damier est flou, caché ou mal éclairé.")
                    
            elif key == ord('q'): # Touche Q
                print("\n[INFO] Arrêt demandé par l'utilisateur.")
                break

    except KeyboardInterrupt:
        print("\n\n[INFO] Capture interrompue (Ctrl+C).")
    
    finally:
        picam2.stop()
        picam2.close()
        cv2.destroyAllWindows()
        print("\n" + "="*50)
        print(f"📸 TERMINÉ ! {photos_taken} photos ont été sauvegardées dans '{SAVE_DIR}/'.")
        print("Pour calculer la matrice, lancez : python tools/calibrate_camera.py")
        print("="*50)

if __name__ == "__main__":
    main()