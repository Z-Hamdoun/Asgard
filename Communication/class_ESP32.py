import serial
import time
import threading

class ESP32_Link:
    """
    Gère la communication UART avec l'ESP32.
    Format du protocole texte :
    - CFG:lat:lng:alt   -> Envoi de configuration
    - CMD:START         -> Ordre de démarrage
    - GPS:lat:lng:alt   -> Télémétrie en vol
    """
    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 115200, mock_simulation: bool = False):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.connected = False
        self.mock = mock_simulation
        
        # Variables de stockage des réceptions
        self.derniere_commande = None
        self.derniere_config = None
        self.valhalla_lat = None
        self.valhalla_lon = None
        self.valhalla_alt = None
        
        self.lock = threading.Lock()

    def connect(self) -> bool:
        if self.mock:
            print(f"[ESP32] Mode SIMULATION activé (Fausse connexion)")
            self.connected = True
            return True
            
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            self.connected = True
            print(f"[ESP32] Connecté avec succès sur {self.port}")
            
            t = threading.Thread(target=self._ecoute_continue, daemon=True)
            t.start()
            return True
        except serial.SerialException as e:
            print(f"[ESP32] ERREUR de connexion sur {self.port}: {e}")
            self.connected = False
            return False

    # Methodes d'envoi
    def send_config(self, lat: float, lng: float, alt: float):
        msg = f"CFG:{lat}:{lng}:{alt}\n"
        self._write_serial(msg)
        print(f"[ESP32-TX] Config envoyée : {msg.strip()}")

    def send_start_mission(self):
        msg = "CMD:START\n"
        self._write_serial(msg)
        print("[ESP32-TX] Ordre de démarrage envoyé !")

    def send_telemetry(self, lat: float, lng: float, alt: float):
        msg = f"GPS:{lat}:{lng}:{alt}\n"
        self._write_serial(msg)

    def _write_serial(self, message: str):
        if self.connected and not self.mock and self.serial_conn:
            self.serial_conn.write(message.encode('utf-8'))

    # Methodes de reception 
    def _ecoute_continue(self):
        while self.connected:
            try:
                if self.serial_conn.in_waiting > 0:
                    ligne = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                    if ligne:
                        self._traiter_message(ligne)
            except Exception as e:
                pass
            time.sleep(0.01)

    def _traiter_message(self, message: str):
        with self.lock:
            if message.startswith("CFG:"):
                parts = message.split(":")
                try:
                    self.derniere_config = {
                        "lat_mission": float(parts[1]),
                        "lng_mission": float(parts[2]),
                        "alt_quadrillage": float(parts[3])
                    }
                    print(f"[ESP32-RX] Configuration reçue : {self.derniere_config}")
                except (IndexError, ValueError):
                    pass
                    
            elif message.startswith("CMD:"):
                self.derniere_commande = message.replace("CMD:", "")
                print(f"[ESP32-RX] Commande reçue : {self.derniere_commande}")
                
            elif message.startswith("GPS:"):
                parts = message.split(":")
                try:
                    self.valhalla_lat = float(parts[1])
                    self.valhalla_lon = float(parts[2])
                    self.valhalla_alt = float(parts[3])
                except (IndexError, ValueError):
                    pass

    # Consommation des messages
    def get_and_clear_command(self):
        with self.lock:
            cmd = self.derniere_commande
            self.derniere_commande = None
            return cmd

    def get_and_clear_config(self):
        with self.lock:
            cfg = self.derniere_config
            self.derniere_config = None
            return cfg