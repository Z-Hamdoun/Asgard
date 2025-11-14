from picamera2 import Picamera2
from flask import Flask, Response
import cv2
import numpy as np # Import nécessaire pour le traitement d'array par cv2

app = Flask(__name__)
picam2 = Picamera2()

# Configuration de la caméra pour la capture vidéo
picam2.configure(picam2.create_video_configuration(main={"size": (1280, 720)}))
picam2.start()

def generate_frames():
    while True:
        # Capture d’une image
        # Assurez-vous que picam2 a démarré correctement
        try:
            frame = picam2.capture_array()
        except Exception:
            # Gérer le cas où picam2 n'est pas initialisé
            continue

        # Encodage en JPEG
        # Utilisation de 90 pour la qualité JPEG (peut être ajusté)
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        
        if not ret:
             continue
             
        frame_bytes = buffer.tobytes()
        
        # Génération du flux vidéo au format MJPEG (multipart/x-mixed-replace)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video')
def video():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    # Lancement du serveur sur toutes les interfaces réseau, port 5000
    picam2.stop() # Assurer l'arrêt en cas de réexécution
    try:
        picam2.start() # Redémarrer la caméra juste avant de servir
        app.run(host="0.0.0.0", port=5000)
    except Exception as e:
        print(f"Erreur lors de l'exécution: {e}")
    finally:
        picam2.stop()