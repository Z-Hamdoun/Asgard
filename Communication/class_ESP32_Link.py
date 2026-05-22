import serial
import time
import threading
import json
import socket


class ESP32_Link:
    """
    Gère la communication UART avec l'ESP32.
    Format du protocole texte :
    - CFG:{"lat":48.1,"res":"1080p", ...}
    - CMD:START         -> Ordre de démarrage
    - GPS:lat:lng:alt   -> Télémétrie en vol
    """

    def __init__(
        self,
        port: str = "/dev/ttyAMA1",
        baudrate: int = 115200,
        mock_simulation: bool = False,
        udp_rx_port: int = 5001,
        udp_tx_port: int = 5002,
    ):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.connected = False

        # Paramètres de simulation
        self.mock = mock_simulation
        self.udp_rx_port = udp_rx_port
        self.udp_tx_port = udp_tx_port
        self.sock = None

        # Variables de stockage des réceptions
        self.derniere_commande = None
        self.derniere_config = None
        self.dernier_cgm = None
        self.dernier_num_mission = None  # Numéro de mission reçu via CMD:START:N
        # Parametres pour le mode follow
        self.valhalla_lat = None
        self.valhalla_lon = None
        self.valhalla_alt = None

        # Watchdog de reconnexion automatique
        self.max_retries = 5
        self.retry_interval = 5.0
        self.reconnect_exhausted = threading.Event()
        self._on_fail_cb = (
            None  # callable(attempt: int) appelé à chaque tentative échouée
        )

        self.lock = threading.Lock()

    def set_fail_callback(self, cb):
        """cb(attempt) est appelé à chaque tentative de reconnexion échouée."""
        self._on_fail_cb = cb

    def connect(self) -> bool:
        if self.mock:
            # --- MODE SIMULATION (Radio Virtuelle UDP) ---
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.sock.bind(("127.0.0.1", self.udp_rx_port))
                self.sock.settimeout(
                    1.0
                )  # Pour ne pas bloquer le thread à la fermeture
                self.connected = True

                t = threading.Thread(target=self._ecoute_continue_udp, daemon=True)
                t.start()
                return True
            except Exception as e:
                print(f"[ESP32 SIMU] Erreur de création du pont UDP : {e}")
                return False

        try:
            self.serial_conn = serial.Serial(
                self.port,
                self.baudrate,
                timeout=1,
                dsrdtr=False,
                rtscts=False,  # évite le reset auto de l'ESP32-C3 à l'ouverture
            )
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
    def send_config(self, config_dict):
        """Transforme le dictionnaire complet en texte compact et l'envoie"""
        # separators=(',', ':') permet de retirer les espaces inutiles pour économiser des octets
        json_str = json.dumps(config_dict, separators=(",", ":"))
        msg = f"CFG:{json_str}\n"

        if len(msg) > 240:
            print(
                f"[ESP32-TX] ATTENTION: Configuration trop lourde ({len(msg)} octets). Risque de coupure ESP-NOW."
            )

        self._write_serial(msg)
        print(f"[ESP32-TX] Config JSON envoyée : {json_str}")

    def send_start_mission(self, num_mission: int = 1):
        msg = f"CMD:START:{num_mission}\n"
        self._write_serial(msg)
        print(f"[ESP32-TX] Ordre de démarrage mission {num_mission} envoyé !")

    def send_telemetry(self, lat: float, lng: float, alt: float):
        msg = f"GPS:{lat}:{lng}:{alt}\n"
        self._write_serial(msg)

    def send_cgm(self, cgm_value: int):
        """Envoie un code de mission (CGM) via ESP-NOW"""
        if not self.connected:
            print(f"[ESP32-TX] ERREUR : non connecté, CGM {cgm_value} non envoyé !")
            return
        self._write_serial(f"CGM:{cgm_value}\n")
        print(f"[ESP32-TX] CGM {cgm_value} envoyé.")

    def _write_serial(self, message: str):
        if not self.connected:
            return

        if self.mock and self.sock:
            # Mode Simulation
            self.sock.sendto(message.encode("utf-8"), ("127.0.0.1", self.udp_tx_port))
        elif not self.mock and self.serial_conn:
            # Mode Réel : Envoi par le câble physique UART
            self.serial_conn.write(message.encode("utf-8"))

    # Methodes de reception
    def _ecoute_continue(self):
        error_triggered = False
        while self.connected:
            try:
                if self.serial_conn.in_waiting > 0:
                    ligne = (
                        self.serial_conn.readline()
                        .decode("utf-8", errors="ignore")
                        .strip()
                    )
                    if ligne:
                        self._traiter_message(ligne)
            except Exception as e:
                print(f"[ESP32-UART] Erreur de lecture : {e}")
                self.connected = False
                error_triggered = True
                break
            time.sleep(0.01)
        if error_triggered:
            threading.Thread(target=self._watchdog, daemon=True).start()

    def _watchdog(self):
        """Tente de reconnecter l'ESP32 après une déconnexion inattendue."""
        if self.serial_conn:
            try:
                self.serial_conn.close()
            except Exception:
                pass
            self.serial_conn = None

        for attempt in range(1, self.max_retries + 1):
            print(
                f"[ESP32-WD] Tentative de reconnexion {attempt}/{self.max_retries}..."
            )
            if self._on_fail_cb:
                try:
                    self._on_fail_cb(attempt)
                except Exception:
                    pass
            time.sleep(self.retry_interval)
            if self.connect():
                print(f"[ESP32-WD] Reconnecté après {attempt} tentative(s).")
                self.reconnect_exhausted.clear()
                return

        print(
            f"[ESP32-WD] Reconnexion échouée après {self.max_retries} tentatives. ESP32 considéré perdu."
        )
        self.reconnect_exhausted.set()

    def _ecoute_continue_udp(self):
        while self.connected:
            try:
                data, _ = self.sock.recvfrom(1024)
                if data:
                    ligne = data.decode("utf-8", errors="ignore").strip()
                    if ligne:
                        self._traiter_message(ligne)
            except socket.timeout:
                pass  # Normal, permet de vérifier si on doit fermer le thread
            except Exception:
                pass

    def _traiter_message(self, message: str):
        with self.lock:
            # Si on recoit une config json
            if message.startswith("CFG:"):
                json_str = message[4:]  # On retire "CFG:"
                try:
                    self.derniere_config = json.loads(json_str)
                    print(
                        f"[ESP32-RX] Configuration JSON reçue : {self.derniere_config}"
                    )
                except json.JSONDecodeError:
                    print(f"[ESP32-RX] Erreur : JSON corrompu reçu -> {json_str}")

            elif message.startswith("CGM:"):  # Interception d'un CGM
                try:
                    self.dernier_cgm = int(message.split(":")[1])
                    print(
                        f"[ESP32-RX] CGM intercepté depuis l'essaim : {self.dernier_cgm}"
                    )
                except ValueError:
                    pass

            elif message.startswith("CMD:"):
                cmd_content = message[4:]  # retire "CMD:"
                if cmd_content.startswith("START"):
                    parts = cmd_content.split(":")
                    try:
                        if len(parts) < 2:
                            raise ValueError("numéro de mission manquant")
                        num = int(parts[1])
                        if num < 1 or num > 5:
                            raise ValueError(f"mission {num} hors limite [1-5]")
                        self.dernier_num_mission = num
                        self.derniere_commande = "START"
                        print(f"[ESP32-RX] Ordre START mission {num} reçu.")
                    except ValueError as e:
                        # Envoi immédiat du CGM d'erreur à Valhalla (408 = VALKYRIE_MISSION_INVALID)
                        print(
                            f"[ESP32-RX] ERREUR CMD:START invalide ({e}) — CGM 408 envoyé à Valhalla !"
                        )
                        self._write_serial("CGM:408\n")
                else:
                    self.derniere_commande = cmd_content
                    print(f"[ESP32-RX] Commande reçue : {cmd_content}")

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

    def get_and_clear_cgm(self):
        """Récupère le dernier CGM reçu et vide la variable"""
        with self.lock:
            cgm = self.dernier_cgm
            self.dernier_cgm = None
            return cgm

    def get_and_clear_mission_start(self) -> "int | None":
        """
        Retourne le numéro de mission (int >= 1) si un ordre CMD:START:N valide a été reçu.
        Retourne None si aucun ordre START n'est en attente.
        Les erreurs de parsing sont gérées directement dans _traiter_message (CGM 408 envoyé).
        """
        with self.lock:
            if self.derniere_commande == "START":
                num = self.dernier_num_mission
                self.derniere_commande = None
                self.dernier_num_mission = None
                return num
            return None
