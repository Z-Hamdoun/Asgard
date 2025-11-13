import spidev
import time
import cv2
import numpy as np

# --- CONFIGURATION SPI (Esclave) ---
# En mode Esclave, l'ESP32 (Maitre) contrôle la vitesse. 
# Cette configuration est plus complexe et depend de la version du noyau RPi.
# La librairie standard `spidev` ne supporte pas nativement le mode Esclave sur tous les RPi.
# On simule ici la lecture si le support SPI Esclave est fonctionnel.

SPI_BUS = 0
SPI_DEVICE = 1 # Utiliser une autre pin CS pour l'Esclave
SPI_SPEED = 1000000 
SPI_CS_PIN = 27 # Broche GPIO CS/SS pour l'ESP32-B (Maitre)

# Initialisation (assumer le support Esclave ou utiliser un noyau modifié)
spi = spidev.SpiDev(SPI_BUS, SPI_DEVICE)
spi.max_speed_hz = SPI_SPEED
spi.mode = 0b00 

def receive_frame_via_spi():
    """Attend la reception d'une trame binaire de l'ESP32-B (Maitre)."""
    
    # 1. Attendre que l'ESP32-B selectionne le RPi 2 (CS LOW)
    # (Cette logique depend fortement de la configuration GPIO en mode Esclave)

    # 2. Recevoir l'en-tete de taille (4 bytes)
    # On envoie des 'placeholders' (0xFF) pour forcer le Maitre a envoyer
    size_header_list = spi.xfer2([0xFF] * 4) 
    size_header = bytes(size_header_list)
    frame_size = int.from_bytes(size_header, byteorder='little')

    if frame_size > 0 and frame_size < 1024 * 50: # Limite de taille raisonnable (50KB)
        print(f"Trame detectee: {frame_size} bytes.")
        
        # 3. Recevoir le corps de la trame
        data_list = []
        chunk_size = 1024
        for i in range(0, frame_size, chunk_size):
            num_bytes = min(chunk_size, frame_size - i)
            # Creer une liste de 0xFF de la bonne taille pour recevoir les donnees
            placeholder = [0xFF] * num_bytes 
            data_list.extend(spi.xfer2(placeholder))
            
        return bytes(data_list)
        
    return None

# --- BOUCLE PRINCIPALE DE RÉCEPTION ET AFFICHAGE ---
try:
    while True:
        frame_bytes = receive_frame_via_spi()
        
        if frame_bytes:
            # Convertir les bytes JPEG en tableau OpenCV
            np_arr = np.frombuffer(frame_bytes, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if frame is not None:
                cv2.imshow('Flux Video Recu', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        
except KeyboardInterrupt:
    print("Arret de la lecture.")
finally:
    spi.close()
    cv2.destroyAllWindows()