import serial
import threading
import time


class GripperESP32:
    """
    Pilote la pince servo de Valkyrie via l'ESP32-C3 (UART/USB, 115200 baud).

    Protocole : toutes les commandes pince sont préfixées "GRIP:" pour ne pas
    être confondues avec les messages bridge ESP-NOW qui transitent sur le même port.

    Envoi Pi -->ESP32 :
        GRIP:CALIB   ferme jusqu'au contact, puis ouvre automatiquement (27s)
        GRIP:OPEN    ouvre la pince (27s)
        GRIP:CLOSE   ferme et détecte la saisie
        GRIP:STOP    arrêt d'urgence (recalibration requise ensuite)

    Réception ESP32 -->Pi (parsées) :
        GRIP:READY          ESP32 prêt après boot
        GRIP:CALIB_OK       zéro trouvé, ouverture en cours
        GRIP:OPEN_DONE      pince pleinement ouverte
        GRIP:CONTACT        switch touché, serrage final (2s) en cours
        GRIP:OBJECT_CAUGHT  objet sécurisé (saisie réussie)
        GRIP:TIMEOUT_CALIB  timeout calibration (switch jamais touché en 35s)
        GRIP:TIMEOUT_CLOSE  timeout fermeture (rien saisi en 35s)
        GRIP:STOPPED        arrêt d'urgence effectué
        GRIP:ERR_*          erreur (ex : OPEN envoyé sans calibration)

    Tous les autres messages reçus (non préfixés GRIP:) sont des relais ESP-NOW
    et sont ignorés par cette classe -- ils appartiennent à class_ESP32_Link.
    """

    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 115200):
        self._port     = port
        self._baudrate = baudrate
        self._serial: serial.Serial | None = None
        self._connected = False
        self._write_lock = threading.Lock()

        # Événements pour débloquer les appels bloquants
        self._ev_ready     = threading.Event()
        self._ev_open_done = threading.Event()
        self._ev_caught    = threading.Event()
        self._ev_timeout   = threading.Event()

        self._reader_thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Connexion / déconnexion
    # ------------------------------------------------------------------

    def connect(self, wait_ready: float = 3.0) -> bool:
        """
        Ouvre le port UART et attend le signal GRIP:READY de l'ESP32.
        wait_ready : temps maximum d'attente du signal de boot (secondes).
        """
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

            if not self._ev_ready.wait(timeout=wait_ready):
                # L'ESP32 était peut-être déjà démarré avant la connexion série ;
                # on continue quand même.
                print("[PINCE] Signal GRIP:READY non reçu -- ESP32 déjà démarré ?")

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
        Lance la calibration : ferme jusqu'au contact, puis ouvre (27s).
        Bloque jusqu'à GRIP:OPEN_DONE ou timeout.
        Timeout conseillé ≥ 62s (35s calib max + 27s ouverture).
        Retourne True si OK, False si timeout.
        """
        self._ev_open_done.clear()
        self._send("CALIB")
        if not self._ev_open_done.wait(timeout=timeout):
            print("[PINCE] Timeout calibration.")
            return False
        print("[PINCE] Calibration OK -- pince grande ouverte.")
        return True

    def open_gripper(self, timeout: float = 35.0) -> bool:
        """
        Ouvre la pince. Bloque jusqu'à GRIP:OPEN_DONE (27s) ou timeout.
        Nécessite une calibration préalable.
        """
        self._ev_open_done.clear()
        self._send("OPEN")
        if not self._ev_open_done.wait(timeout=timeout):
            print("[PINCE] Timeout ouverture.")
            return False
        return True

    def close_gripper(self, timeout: float = 40.0) -> bool:
        """
        Ferme la pince et détecte la saisie.
        Bloque jusqu'à :
          True  -- GRIP:OBJECT_CAUGHT (switches actionnés, objet saisi)
          False -- GRIP:TIMEOUT_CLOSE (rien saisi) ou timeout Python
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

    def _send(self, sub_cmd: str):
        """Envoie une commande pince avec le préfixe GRIP:."""
        if not self._connected or self._serial is None:
            print(f"[PINCE] Non connectée -- commande '{sub_cmd}' ignorée.")
            return
        msg = f"GRIP:{sub_cmd}\n"
        with self._write_lock:
            self._serial.write(msg.encode("utf-8"))
        print(f"[PINCE-TX] GRIP:{sub_cmd}")

    def _read_loop(self):
        while self._connected:
            try:
                if self._serial.in_waiting > 0:
                    raw = self._serial.readline().decode("utf-8", errors="ignore").strip()
                    if raw.startswith("GRIP:"):
                        self._parse_grip_line(raw[5:])  # retire le préfixe "GRIP:"
                    # Les autres lignes (relais ESP-NOW) sont ignorées ici
            except Exception as e:
                print(f"[PINCE-UART] Erreur lecture : {e}")
                self._connected = False
                break
            time.sleep(0.01)

    def _parse_grip_line(self, payload: str):
        """Traite la partie après 'GRIP:' dans un message de l'ESP32."""
        print(f"[PINCE-RX] GRIP:{payload}")
        if payload == "READY":
            self._ev_ready.set()
        elif payload == "OPEN_DONE":
            self._ev_open_done.set()
        elif payload == "OBJECT_CAUGHT":
            self._ev_caught.set()
        elif payload in ("TIMEOUT_CALIB", "TIMEOUT_CLOSE"):
            self._ev_timeout.set()
