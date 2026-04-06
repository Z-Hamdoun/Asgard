import sys
import os
import cv2
import cv2.aruco as aruco
import numpy as np
import subprocess
import argparse
import time
from picamera2 import Picamera2

def main():
    parser = argparse.ArgumentParser(description="Live Stream ArUco avec HUD (Headless)")
    parser.add_argument("--ip", required=True, help="Adresse IP du PC (ex: 192.168.1.50)")
    parser.add_argument("--port", type=int, default=5000, help="Port UDP (défaut: 5000)")
    args = parser.parse_args()

    UDP_IP = args.ip
    UDP_PORT = args.port
    RESOLUTION = (640, 480)

    print(f"[STREAM] Démarrage du flux vers udp://{UDP_IP}:{UDP_PORT}")

    # Configuration optimisée de FFMPEG pour la très basse latence (H264)
    # Les paramètres -g 30 et -profile:v baseline sont vitaux pour corriger l'erreur PPS
    ffmpeg_cmd = [
        "ffmpeg",
        "-y",                 # Écraser la sortie
        "-f", "rawvideo",     # Format d'entrée brut
        "-vcodec", "rawvideo",
        "-pix_fmt", "bgr24",  # Format couleur OpenCV
        "-s", f"{RESOLUTION[0]}x{RESOLUTION[1]}",
        "-r", "30",           # Framerate
        "-i", "-",            # Lire depuis l'entrée standard (stdin)
        "-c:v", "libx264",    # Encodage H264 (bien meilleur que mpeg1)
        "-preset", "ultrafast", # Pour la latence minimale
        "-tune", "zerolatency", # Optimisation temps réel
        "-profile:v", "baseline", # Évite les B-frames complexes (meilleur pour UDP)
        "-g", "30",           # Force un Keyframe toutes les 30 frames (corrige l'erreur PPS 0)
        "-f", "mpegts",       # Conteneur transport stream
        f"udp://{UDP_IP}:{UDP_PORT}?pkt_size=1316"
    ]

    # Lancement du processus FFMPEG
    try:
        ffmpeg = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print("[ERREUR] ffmpeg n'est pas installé sur ce système. (sudo apt install ffmpeg)")
        sys.exit(1)

    # =========================================================================
    # 1. INITIALISATION CAMÉRA (PiCamera2 directe, sans classe Camera)
    # =========================================================================
    print("[STREAM] Initialisation de la PiCamera2...")
    picam2 = Picamera2()
    picam2.preview_configuration.main.size = RESOLUTION
    picam2.preview_configuration.main.format = "RGB888"
    picam2.preview_configuration.controls.FrameRate = 30
    picam2.configure("preview")
    picam2.start()
    picam2.set_controls({"AeEnable": True, "ExposureValue": -1})
    time.sleep(2) # Temps de chauffe

    # =========================================================================
    # 2. CONFIGURATION ARUCO (Extraction de ta logique)
    # =========================================================================
    aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_6X6_250)
    aruco_params = aruco.DetectorParameters()
    marker_size = 0.36 # Taille de ton ArUco en mètres

    # Matrice Caméra V3 (FOV large, focale ~420 pour 640x480)
    camera_matrix = np.array([
        [420.0,   0.0, 320.0],
        [  0.0, 420.0, 240.0],
        [  0.0,   0.0,   1.0]
    ], dtype=np.float64)
    dist_coeffs = np.zeros((5, 1), dtype=np.float64)

    try:
        while True:
            # --- CAPTURE ---
            # picam2 renvoie du RGB, OpenCV utilise du BGR
            frame_rgb = picam2.capture_array()
            frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

            # --- ANALYSE ARUCO ---
            corners, ids, _ = aruco.detectMarkers(gray, aruco_dict, parameters=aruco_params)

            info = None
            dx, dy, dz = 0.0, 0.0, 0.0
            cx, cy = RESOLUTION[0] // 2, RESOLUTION[1] // 2

            if ids is not None and len(ids) > 0:
                # On prend le premier marqueur trouvé
                corner = corners[0]
                aruco_id = ids[0][0]

                # Estimation de pose
                _, tvec, _ = aruco.estimatePoseSingleMarkers([corner], marker_size, camera_matrix, dist_coeffs)
                tvec = tvec[0][0]

                # Conversion Repère Caméra -> Repère Drone (Identique à ton _camera_to_drone)
                dx = float(tvec[1])   # X Drone (Avant) = Y Caméra
                dy = -float(tvec[0])  # Y Drone (Droite) = -X Caméra
                dz = float(tvec[2])   # Z Drone (Bas) = Z Caméra

                info = str(aruco_id)

                # Dessiner le carré autour du tag sur l'image
                cv2.aruco.drawDetectedMarkers(frame_bgr, corners, ids)

            # --- DESSIN DU HUD ---
            if info is not None:
                # --- ARUCO DÉTECTÉ ---
                color = (0, 255, 0) # Vert
                cv2.putText(frame_bgr, f"TARGET LOCKED (ID {info})", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                cv2.putText(frame_bgr, f"X: {dx:.2f}m | Y: {dy:.2f}m | Z: {dz:.2f}m", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

                # Réticule dynamique
                target_x = int(cx + (dy * 100))
                target_y = int(cy - (dx * 100))
                cv2.circle(frame_bgr, (target_x, target_y), 15, color, 2)
                cv2.line(frame_bgr, (cx, cy), (target_x, target_y), color, 1)

            else:
                # --- RECHERCHE ---
                color = (0, 0, 255) # Rouge
                cv2.putText(frame_bgr, "SEARCHING ARUCO...", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

            # Croix centrale fixe
            cv2.line(frame_bgr, (cx - 20, cy), (cx + 20, cy), (255, 255, 255), 2)
            cv2.line(frame_bgr, (cx, cy - 20), (cx, cy + 20), (255, 255, 255), 2)

            # --- ENVOI AU FLUX VIDÉO ---
            try:
                ffmpeg.stdin.write(np.ascontiguousarray(frame_bgr).tobytes())
            except BrokenPipeError:
                print("[ERREUR] Le flux FFMPEG s'est interrompu (Broken Pipe).")
                break

    except KeyboardInterrupt:
        print("\n[STREAM] Arrêt demandé.")
    finally:
        # Nettoyage ultra-sécurisé (PAS DE destroyAllWindows ici !)
        picam2.stop()
        picam2.close()
        ffmpeg.stdin.close()
        ffmpeg.wait()
        print("[STREAM] Terminé.")

if __name__ == "__main__":
    main()