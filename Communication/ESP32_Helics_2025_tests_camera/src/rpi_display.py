import socket
import struct
import cv2
import numpy as np

# --- Configuration ---
RELAY_IP = '192.168.1.12' # <--- IP de l'ESP32-2
RELAY_PORT = 8002
# ---------------------

def start_client():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((RELAY_IP, RELAY_PORT))
    print(f"Connecté au Relais ESP32-2 à {RELAY_IP}:{RELAY_PORT}")
    
    # Méthode pour lire exactement N octets
    def recvall(sock, count):
        buf = b''
        while count:
            newbuf = sock.recv(count)
            if not newbuf: return None
            buf += newbuf
            count -= len(newbuf)
        return buf

    try:
        while True:
            # 1. Recevoir la taille de l'image (8 octets)
            image_size_bytes = recvall(client_socket, 8)
            if not image_size_bytes:
                break
                
            image_size = int.from_bytes(image_size_bytes, byteorder='big')
            
            # 2. Recevoir les données JPEG brutes
            jpeg_data = recvall(client_socket, image_size)
            if not jpeg_data:
                break
            
            # 3. Décompresser et afficher l'image avec OpenCV
            image_array = np.frombuffer(jpeg_data, dtype=np.uint8)
            frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

            cv2.imshow('Video Stream', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        print("Fermeture du client.")
        client_socket.close()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    start_client()