import spidev
import time
import cv2
from picamera2 import Picamera2 # Pour la capture video

# --- CONFIGURATION SPI (Maitre) ---
SPI_BUS = 0
SPI_DEVICE = 0 
SPI_SPEED = 1000000 # 1 MHz (ajustez pour la performance)
SPI_CS_PIN = 26 # Broche GPIO pour le Chip Select vers ESP32-A (Esclave)

# --- CONFIGURATION VIDÉO ---
CAPTURE_SIZE = (640, 480)
# Taux de compression JPEG (0-100, plus bas = plus petit/moins qualite)
JPEG_QUALITY = 50 

# Initialisation
spi = spidev.SpiDev(SPI_BUS, SPI_DEVICE)
spi.max_speed_hz = SPI_SPEED
spi.mode = 0b00 # Mode SPI 0

# Configuration du Chip Select (via GPIO)
# Nécessite un setup GPIO (ex: RPi.GPIO)
# import RPi.GPIO as GPIO
# GPIO.setmode(GPIO.BCM)
# GPIO.setup(SPI_CS_PIN, GPIO.OUT)
# GPIO.output(SPI_CS_PIN, GPIO.HIGH) # Desactiver initialement

picam2 = Picamera2()
config = picam2.create_video_configuration(main={"size": CAPTURE_SIZE})
picam2.configure(config)
picam2.start()

def send_frame_via_spi(frame_bytes):
    """Envoie une trame video complete a l'ESP32-A (Esclave SPI)."""
    
    frame_size = len(frame_bytes)
    # L'ESP32 est en C/C++, on encode la taille sur 4 bytes (little-endian)
    size_header = frame_size.to_bytes(4, byteorder='little') 

    # GPIO.output(SPI_CS_PIN, GPIO.LOW) # 1. Selectionner l'Esclave (ESP32-A)

    try:
        # Envoi de l'en-tete de taille
        spi.xfer2(list(size_header))
        
        # Envoi des donnees de la trame (par paquets pour gerer la taille du buffer SPI)
        chunk_size = 1024 
        for i in range(0, frame_size, chunk_size):
            chunk = frame_bytes[i:i + chunk_size]
            # spi.xfer2 prend une liste d'octets
            spi.xfer2(list(chunk))
        
        print(f"Trame JPEG envoyee: {frame_size} bytes.")

    except Exception as e:
        print(f"Erreur SPI: {e}")
        
    # GPIO.output(SPI_CS_PIN, GPIO.HIGH) # 2. Deselectionner l'Esclave

# --- BOUCLE PRINCIPALE D'ENVOI ---
try:
    while True:
        # Capture de la trame
        frame = picam2.capture_array() 
        
        # Encodage en JPEG (format binaire compressé)
        success, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        if success:
            frame_bytes = buffer.tobytes()
            send_frame_via_spi(frame_bytes)

        time.sleep(0.05) # ~20 FPS

except KeyboardInterrupt:
    print("Arret de la capture.")
finally:
    picam2.stop()
    spi.close()
    # GPIO.cleanup()