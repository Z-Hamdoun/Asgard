import serial
import threading
import time


class GripperESP32:
    """
    Pilote la pince servo de Valkyrie via son ESP32 dédié (UART, 115200 baud).

    Protocole texte (envoi PC --> ESP32) :
        CALIB  : trouve le zéro (ferme jusqu'au switch), puis ouvre automatiquement
        OPEN   : ouvre la pince pendant 27s
        CLOSE  : ferme et détecte la saisie via les switches
        STOP   : arrêt d'urgence (nécessite une recalibration ensuite)

    Réponses ESP32 --> PC parsées :
        "Zéro OK"              --> calibration trouvée, ouverture lancée
        "Pince grande ouverte" --> pince pleinement ouverte
        "OBJET SECURISE"       --> switches actionnés, objet saisi
        "TIMEOUT"              --> fermeture sans contact (rien saisi ou calib échouée)
    """

    # Sous-chaînes attendues dans les messages de l'ESP32
    _MSG_CALIB_OK  = "Zéro OK"
    _MSG_OPEN_DONE = "Pince grande ouverte"
    _MSG_CAUGHT    = "OBJET SECURISE"
    _MSG_TIMEOUT   = "TIMEOUT"

    def __init__(self, port: str = "/dev/ttyUSB1", baudrate: int = 115200):
        self._port     = port
        self._baudrate = baudrate
        self._serial: serial.Serial | None = None
        self._connected = False
        self._write_lock = threading.Lock()

        # Événements pour débloquer les appels bloquants
        self._ev_open_done = threading.Event()
        self._ev_caught    = threading.Event()
        self._ev_timeout   = threading.Event()

        self._reader_thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Connexion / déconnexion
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        """Ouvre le port UART et démarre le thread de lecture."""
        try:
            self._serial = serial.Serial(
                self._port, self._baudrate, timeout=1,
                dsrdtr=False, rtscts=False,
            )
            self._connected = True
            self._reader_thread = threading.Thread(
                target=self._read_loop, daemon=True, name="gripper-reader"
            )
            self._reader_thread.start()
            time.sleep(0.5)  # laisser l'ESP32 envoyer son banner de démarrage
            print(f"[PINCE] Connectée sur {self._port}")
            return True
        except Exception as e:
            print(f"[PINCE] Connexion impossible sur {self._port} : {e}")
            return False

    def close(self):
        """Ferme proprement le port UART."""
        self._connected = False
        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Commandes principales (bloquantes)
    # ------------------------------------------------------------------

    def calibrate(self, timeout: float = 70.0) -> bool:
        """
        Lance la calibration : ferme jusqu'au contact, puis ouvre pendant 27s.
        Bloque jusqu'à ce que la pince soit grande ouverte ou que le timeout expire.

        Timeout conseillé > 62s (35s calib max + 27s ouverture).
        Retourne True si calibration + ouverture OK, False si timeout.
        """
        self._ev_open_done.clear()
        self._send("CALIB")
        if not self._ev_open_done.wait(timeout=timeout):
            print("[PINCE] Timeout calibration.")
            return False
        print("[PINCE] Calibration OK — pince grande ouverte.")
        return True

    def open_gripper(self, timeout: float = 35.0) -> bool:
        """
        Ouvre la pince. Bloque jusqu'à pleine ouverture (27s) ou timeout.
        Nécessite une calibration préalable.
        Retourne True quand pleinement ouverte.
        """
        self._ev_open_done.clear()
        self._send("OPEN")
        if not self._ev_open_done.wait(timeout=timeout):
            print("[PINCE] Timeout ouverture.")
            return False
        return True

    def close_gripper(self, timeout: float = 40.0) -> bool:
        """
        Ferme la pince et vérifie la saisie via les switches.
        Bloque jusqu'à l'un des deux résultats :
          - True  : "OBJET SECURISE" (les deux mâchoires ont actionné un switch)
          - False : "TIMEOUT" (fermeture sans contact --> rien saisi)
        Nécessite une calibration préalable.
        """
        self._ev_caught.clear()
        self._ev_timeout.clear()
        self._send("CLOSE")
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._ev_caught.wait(timeout=0.1):
                return True
            if self._ev_timeout.is_set():
                return False
        print("[PINCE] Timeout fermeture (côté Python).")
        return False

    def stop(self):
        """Arrêt d'urgence. Une recalibration sera nécessaire avant la prochaine action."""
        self._send("STOP")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _send(self, cmd: str):
        if not self._connected or self._serial is None:
            print(f"[PINCE] Non connectée — commande '{cmd}' ignorée.")
            return
        with self._write_lock:
            self._serial.write((cmd + "\n").encode("utf-8"))
        print(f"[PINCE-TX] {cmd}")

    def _read_loop(self):
        while self._connected:
            try:
                if self._serial.in_waiting > 0:
                    raw = self._serial.readline().decode("utf-8", errors="ignore").strip()
                    if raw:
                        self._parse_line(raw)
            except Exception as e:
                print(f"[PINCE-UART] Erreur lecture : {e}")
                self._connected = False
                break
            time.sleep(0.01)

    def _parse_line(self, line: str):
        print(f"[PINCE-RX] {line}")
        if self._MSG_OPEN_DONE in line:
            self._ev_open_done.set()
        if self._MSG_CAUGHT in line:
            self._ev_caught.set()
        if self._MSG_TIMEOUT in line:
            self._ev_timeout.set()
