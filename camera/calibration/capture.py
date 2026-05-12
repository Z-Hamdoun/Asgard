import os
import cv2
import numpy as np
from picamera2 import Picamera2

# ==========================================================
# CONFIGURATION
# ==========================================================
CHESSBOARD_SIZE = (9, 6) 
SAVE_DIR = "images_calib"
MAX_PHOTOS = 30        

def main():
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)
        print(f"[INFO] Dossier {SAVE_DIR}/ créé.")

    print("[INFO] Démarrage de la caméra (Forçage du FOV Wide 120°)...")
    picam2 = Picamera2()
    
    # Configuration avec le hack "lores" pour le plein FOV
    config = picam2.create_video_configuration(
        main={"size": (848, 480), "format": "RGB888"},
        lores={"format": "YUV420"} 
    )
    
    picam2.configure(config)
    picam2.start()
    
    picam2.set_controls({
        "AeEnable": True, 
        "ExposureValue": 0,
        "FrameRate": 30
    })

    print("\n" + "="*50)
    print("📸 ASSISTANT DE CALIBRATION (VUE GRAND ANGLE)")
    print("="*50)
    print("-> La fenêtre vidéo va s'ouvrir.")
    print("-> APPUYEZ SUR [ESPACE] pour prendre une photo.")
    print("-> APPUYEZ SUR [Q] pour quitter le programme.")
    print("="*50 + "\n")

    photos_taken = 0

    try:
        while photos_taken < MAX_PHOTOS:
            # Capture sur le flux "lores" pour le 848x480 non rogné
            frame_rgb = picam2.capture_array("lores")
            frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            
            # Copie pour l'affichage (afin de ne pas sauvegarder les dessins)
            display_frame = frame_bgr.copy()

            # Recherche du damier
            ret, corners = cv2.findChessboardCorners(gray, CHESSBOARD_SIZE, None)

            if ret:
                # Dessin du motif arc-en-ciel
                cv2.drawChessboardCorners(display_frame, CHESSBOARD_SIZE, corners, ret)
                cv2.putText(display_frame, "DAMIER DETECTE -> ESPACE", (10, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            else:
                cv2.putText(display_frame, "RECHERCHE DU DAMIER...", (10, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

            cv2.putText(display_frame, f"Photos : {photos_taken}/{MAX_PHOTOS}", (10, 460), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            cv2.imshow("Calibration Camera - FOV 120", display_frame)

            key = cv2.waitKey(1) & 0xFF
            
            if key == ord(' '): 
                if ret:
                    filepath = os.path.join(SAVE_DIR, f"calib_{photos_taken+1:02d}.jpg")
                    cv2.imwrite(filepath, frame_bgr)
                    photos_taken += 1
                    print(f"✅ Photo {photos_taken}/{MAX_PHOTOS} sauvegardée !")
                    
                    # Flash blanc de confirmation
                    flash = np.ones_like(display_frame) * 255
                    cv2.imshow("Calibration Camera - FOV 120", flash)
                    cv2.waitKey(100)
                else:
                    print("⚠️ Impossible de capturer : le damier est flou ou caché.")
                    
            elif key == ord('q'):
                print("\n[INFO] Arrêt demandé par l'utilisateur.")
                break

    except KeyboardInterrupt:
        print("\n\n[INFO] Capture interrompue (Ctrl+C).")
    
    finally:
        picam2.stop()
        picam2.close()
        cv2.destroyAllWindows()
        print("\n[INFO] Fin de capture. Relancez calibrate.py")

if __name__ == "__main__":
    main()