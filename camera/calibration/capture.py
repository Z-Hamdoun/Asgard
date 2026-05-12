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

    print("[INFO] Démarrage de la caméra (Forçage du FOV Wide 120°)...")
    picam2 = Picamera2()
    
    # L'ASTUCE EST ICI : 
    # On force le capteur à s'ouvrir en grand avec le main stream (1080p)
    # Et on récupère l'image redimensionnée (sans crop !) via le lores stream
    config = picam2.create_video_configuration(
        main={"size": (1920, 1080), "format": "RGB888"},
        lores={"size": (848, 480), "format": "RGB888"}
    )
    
    picam2.configure(config)
    picam2.start()
    
    picam2.set_controls({
        "AeEnable": True, 
        "ExposureValue": 0,
        "FrameRate": 30
    })

    print("\n" + "="*50)
    print("📸 CAPTURE AUTOMATIQUE (MODE WIDE FORCE)")
    print("="*50)
    print("-> Bougez le damier entre chaque 'BIP !'")
    print("="*50 + "\n")

    photos_taken = 0
    last_capture_time = 0

    try:
        while photos_taken < MAX_PHOTOS:
            # IMPORTANT : On capture le flux "lores" pour avoir notre 848x480 grand angle !
            frame_rgb = picam2.capture_array("lores")
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
        print("\n\n[INFO] Capture interrompue par l'utilisateur.")
    
    finally:
        picam2.stop()
        picam2.close()
        print("\n[INFO] Fin de capture. Relancez calibrate.py")

if __name__ == "__main__":
    main()