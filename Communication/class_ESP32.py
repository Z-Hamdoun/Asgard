import serial
import time
import threading

class ESP32_Link:
    """
    Gère la communication série avec l'ESP32.
    L'ESP32 est programmé pour relayer de manière transparente les messages
    UART vers le protocole radio ESP-NOW, et inversement.
    """
    def __init__(self, port: str = "/dev/ttyACM0", baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.connected = False
        
        self.dernier_message_recu = ""
        self.lock = threading.Lock()
        
        # Coordonnées GPS de Valhalla mises à jour en direct pendant le Follow
        self.valhalla_lat = None
        self.valhalla_lon = None
        self.valhalla_alt = None

    def connect(self) -> bool:
        """Tente d'ouvrir le port série vers l'ESP32."""
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            self.connected = True
            print(f"[ESP32] Connecté avec succès sur {self.port}")
            
            # Lancement du thread d'écoute continue
            t = threading.Thread(target=self._ecoute_continue, daemon=True)
            t.start()
            return True
        except serial.SerialException as e:
            print(f"[ESP32] Erreur de connexion sur {self.port}: {e}")
            self.connected = False
            return False

    def send_message(self, message: str):
        """Envoie un message texte à l'ESP32 (qui le crachera via ESP-NOW)."""
        if self.connected and self.serial_conn:
            msg_bytes = (message + "\n").encode('utf-8')
            self.serial_conn.write(msg_bytes)

    def get_last_message(self) -> str:
        """Récupère le dernier message et vide le buffer."""
        with self.lock:
            msg = self.dernier_message_recu
            self.dernier_message_recu = ""
            return msg

    def _ecoute_continue(self):
        """Thread tournant en tâche de fond pour écouter l'ESP32."""
        while self.connected:
            try:
                if self.serial_conn.in_waiting > 0:
                    ligne = self.serial_conn.readline().decode('utf-8').strip()
                    if ligne:
                        self._traiter_message(ligne)
            except Exception as e:
                print(f"[ESP32] Erreur de lecture : {e}")
                time.sleep(1)
            time.sleep(0.01) # Petite pause pour ne pas surcharger le CPU

    def _traiter_message(self, message: str):
        """Analyse le contenu du message reçu via ESP-NOW."""
        # Si c'est un message de commande système (ex: START_MISSION)
        if message.startswith("CMD:"):
            with self.lock:
                self.dernier_message_recu = message.replace("CMD:", "")
                
        # Si c'est un flux télémétrique GPS (ex: GPS:48.7,-2.1,15)
        elif message.startswith("GPS:"):
            try:
                parts = message.replace("GPS:", "").split(",")
                self.valhalla_lat = float(parts[0])
                self.valhalla_lon = float(parts[1])
                self.valhalla_alt = float(parts[2])
            except (IndexError, ValueError):
                pass