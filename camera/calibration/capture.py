import os
import cv2
import numpy as np
import time
from picamera2 import Picamera2

# ==========================================================
# CONFIGURATION 
# ==========================================================
CHESSBOARD_SIZE = (9, 6) 
SAVE_DIR = "images_calib"
MAX_PHOTOS = 30        
COOLDOWN = 2.0         

def main():
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)
        print(f"[INFO] Dossier {SAVE_DIR}/ créé.")

    print("[INFO] Démarrage de la caméra en mode FOV COMPLET (120°)...")
    picam2 = Picamera2()
    
    # =========================================================================
    # LE CORRECTIF MAGIQUE EST ICI
    # On force le plein capteur (Video) + RGB pour nous + YUV pour le système
    # =========================================================================
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
    print("📸 CAPTURE AUTOMATIQUE 120° (MODE SANS ÉCRAN)")
    print("="*50)
    print("-> L'algorithme cherche le damier en permanence.")
    print(f"-> Dès qu'il le voit, il prend une photo et attend {COOLDOWN} secondes.")
    print("-> Bougez le damier entre chaque 'BIP !' pour varier les angles.")
    print("="*50 + "\n")

    photos_taken = 0
    last_capture_time = 0

    try:
        while photos_taken < MAX_PHOTOS:
            frame_rgb = picam2.capture_array("main")
            frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

            ret, corners = cv2.findChessboardCorners(gray, CHESSBOARD_SIZE, None)
            current_time = time.time()
            
            if ret and (current_time - last_capture_time > COOLDOWN):
                filepath = os.path.join(SAVE_DIR, f"calib_{photos_taken+1:02d}.jpg")
                cv2.imwrite(filepath, frame_bgr)
                
                photos_taken += 1
                last_capture_time = current_time
                
                print(f"✅ [BIP !] Photo {photos_taken}/{MAX_PHOTOS} sauvegardée.")
            
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n\n[INFO] Capture interrompue par l'utilisateur (Ctrl+C).")
    
    finally:
        picam2.stop()
        picam2.close()
        print("\n" + "="*50)
        print("📸 TERMINÉ ! Lancez la calibration pour voir votre nouvelle matrice FOV 120° !")
        print("="*50)

if __name__ == "__main__":
    main()