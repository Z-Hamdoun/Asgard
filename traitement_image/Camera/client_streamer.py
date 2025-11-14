import cv2
import time

# --- Configuration du Flux ---

# ATTENTION : Remplacez par l'adresse IP réelle de votre Raspberry Pi
# Elle doit correspondre à l'hôte sur lequel le script camera_streamer.py est lancé.
raspberry_ip = "192.168.1.100" 

# URL complète du flux MJPEG exposé par Flask
url = f"http://{raspberry_ip}:5000/video"

# Initialisation de la capture vidéo
# OpenCV va se connecter au flux MJPEG via l'URL HTTP.
print(f"Tentative de connexion au flux vidéo à l'URL : {url}")
cap = cv2.VideoCapture(url)

# Vérification que l'objet de capture a pu s'ouvrir
if not cap.isOpened():
    print(f"Erreur: Impossible d'ouvrir le flux à l'URL {url}.")
    print("Vérifiez que le script Flask est en cours d'exécution sur le Raspberry Pi et que l'adresse IP est correcte.")
    exit()

# --- Boucle de Lecture et Affichage ---
while True:
    # Lecture d'une image (frame) à partir du flux
    ret, frame = cap.read()

    # Si la lecture échoue (ret est False), c'est que le flux a été perdu ou s'est terminé
    if not ret:
        print("Avertissement: Flux perdu ou terminé. Réessai dans 1 seconde...")
        time.sleep(1)
        # On continue la boucle pour tenter de se reconnecter/récupérer la frame suivante
        continue

    # Affichage de la frame dans une fenêtre nommée "Flux RPi"
    cv2.imshow("Flux RPi", frame)

    # Logique pour quitter la boucle : 
    # Attend 1 milliseconde pour un événement clavier et vérifie si la touche 'q' a été pressée
    if cv2.waitKey(1) & 0xFF == ord('q'):
        print("Fermeture demandée par l'utilisateur.")
        break

# --- Nettoyage ---
# Libère la ressource de capture vidéo
cap.release()
# Ferme toutes les fenêtres OpenCV
cv2.destroyAllWindows()