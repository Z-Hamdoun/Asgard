import io
import socket
import time
from picamera import PiCamera

# --- Configuration ---
SERVER_IP = '0.0.0.0'   # Écoute sur toutes les interfaces
SERVER_PORT = 8000
CONNECTION_DELAY = 10   # Délai pour que l'ESP32 se connecte
# ---------------------

def start_server():
    server_socket = socket.socket()
    server_socket.bind((SERVER_IP, SERVER_PORT))
    server_socket.listen(0)
    print(f"Server démarré sur {SERVER_IP}:{SERVER_PORT}. En attente de connexion...")

    # Attente de la connexion client (ESP32-1)
    client_connection, client_address = server_socket.accept()
    print(f"Connecté à {client_address}")

    # Initialisation de la caméra
    camera = PiCamera()
    camera.resolution = (640, 480)
    camera.framerate = 10
    time.sleep(2) # Laisse le temps à la caméra de s'initialiser

    try:
        stream = io.BytesIO()
        for _ in camera.capture_continuous(stream, 'jpeg', use_video_port=True):
            # Obtient la taille de l'image
            image_size = stream.tell()
            
            # --- Envoi de la taille (8 octets, format fixe) ---
            size_bytes = image_size.to_bytes(8, byteorder='big')
            client_connection.sendall(size_bytes)
            
            # --- Envoi des données JPEG brutes ---
            stream.seek(0)
            client_connection.sendall(stream.read())
            
            # Réinitialisation du buffer pour la prochaine image
            stream.seek(0)
            stream.truncate()

    finally:
        print("Fermeture de la connexion et de la caméra.")
        client_connection.close()
        server_socket.close()
        camera.close()

if __name__ == '__main__':
    start_server()