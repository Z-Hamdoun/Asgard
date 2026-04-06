import sys
import os
import cv2
import numpy as np
import subprocess
import argparse
import time

# Permet d'importer la classe Camera si le script est dans un sous-dossier
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
from Camera.class_Camera import Camera

def main():
    parser = argparse.ArgumentParser(description="Live Stream ArUco avec HUD")
    parser.add_argument("--ip", required=True, help="Adresse IP du PC (ex: 192.168.1.50)")
    parser.add_argument("--port", type=int, default=5000, help="Port UDP (défaut: 5000)")
    args = parser.parse_args()

    UDP_IP = args.ip
    UDP_PORT = args.port
    RESOLUTION = (640, 480)

    print(f"[STREAM] Démarrage du flux vers udp://{UDP_IP}:{UDP_PORT}")

    # Configuration optimisée de FFMPEG pour la très basse latence (H264)
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
        "-f", "mpegts",       # Conteneur transport stream
        f"udp://{UDP_IP}:{UDP_PORT}?pkt_size=1316"
    ]

    # Lancement du processus FFMPEG
    try:
        ffmpeg = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print("[ERREUR] ffmpeg n'est pas installé sur ce système. (sudo apt install ffmpeg)")
        sys.exit(1)

    camera = Camera(simulation=None)
    time.sleep(2) 

    try:
        while True:
            dx, dy, dz, info, frame = camera.analyse(affichage=False)

            if frame is None:
                frame = camera.get_frame(affiche=False)
                if frame is None:
                    continue
                
                if len(frame.shape) == 3:
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            if frame.shape[:2] != (RESOLUTION[1], RESOLUTION[0]):
                frame = cv2.resize(frame, RESOLUTION, interpolation=cv2.INTER_LINEAR)

            if len(frame.shape) == 2:
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            else:
                frame_bgr = frame

            cx, cy = RESOLUTION[0] // 2, RESOLUTION[1] // 2

            if info is not None:
                color = (0, 255, 0)
                
                aruco_id = info.split(',')[0].split(':')[1]
                
                # Textes
                cv2.putText(frame_bgr, f"TARGET LOCKED (ID {aruco_id})", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                cv2.putText(frame_bgr, f"X: {dx:.2f}m | Y: {dy:.2f}m | Z: {dz:.2f}m", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

                target_x = int(cx + (dy * 100))
                target_y = int(cy - (dx * 100))
                
                # Dessin de la cible
                cv2.circle(frame_bgr, (target_x, target_y), 15, color, 2)
                cv2.line(frame_bgr, (cx, cy), (target_x, target_y), color, 1)

            else:
                color = (0, 0, 255)
                cv2.putText(frame_bgr, "SEARCHING ARUCO...", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

            # Croix centrale fixe (Position du drone)
            cv2.line(frame_bgr, (cx - 20, cy), (cx + 20, cy), (255, 255, 255), 2)
            cv2.line(frame_bgr, (cx, cy - 20), (cx, cy + 20), (255, 255, 255), 2)

            # Envoi au flux vidéo
            try:
                ffmpeg.stdin.write(np.ascontiguousarray(frame_bgr).tobytes())
            except BrokenPipeError:
                print("[ERREUR] Le flux FFMPEG s'est interrompu (Broken Pipe).")
                break

    except KeyboardInterrupt:
        print("\n[STREAM] Arrêt demandé.")
    finally:
        camera.close()
        ffmpeg.stdin.close()
        ffmpeg.wait()
        print("[STREAM] Terminé.")

if __name__ == "__main__":
    main()