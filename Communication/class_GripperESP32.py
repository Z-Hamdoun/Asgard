import threading
import time

from Communication.class_ESP32_Link import ESP32_Link


class GripperESP32:
    """
    Pilote la pince servo de Valkyrie via l'ESP32 déjà connecté (ESP32_Link).

    La pince et le bridge ESP-NOW transitent sur le même UART physique (/dev/ttyAMA3).
    GripperESP32 s'enregistre comme callback GRIP: auprès d'ESP32_Link pour recevoir
    les retours de la pince, et envoie ses commandes via ESP32_Link._write_serial.

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
    """

    def __init__(self, esp32_link: ESP32_Link):
        self._esp32 = esp32_link
        self._connected = False

        # Événements pour débloquer les appels bloquants
        self._ev_ready     = threading.Event()
        self._ev_open_done = threading.Event()
        self._ev_caught    = threading.Event()
        self._ev_timeout   = threading.Event()

    # ------------------------------------------------------------------
    # Connexion / déconnexion
    # ------------------------------------------------------------------

    def connect(self, wait_ready: float = 3.0) -> bool:
        """
        Enregistre le callback GRIP: auprès d'ESP32_Link et attend GRIP:READY.
        wait_ready : temps maximum d'attente du signal de boot (secondes).
        """
        if not self._esp32.connected:
            print("[PINCE] ESP32_Link non connecté -- pince indisponible.")
            return False

        self._esp32.set_grip_callback(self._parse_grip_line)
        self._connected = True

        if not self._ev_ready.wait(timeout=wait_ready):
            # L'ESP32 était peut-être déjà démarré avant la connexion ;
            # on continue quand même.
            print("[PINCE] Signal GRIP:READY non reçu -- ESP32 déjà démarré ?")

        print("[PINCE] Connectée (via ESP32_Link)")
        return True

    def close(self):
        """Désenregistre le callback GRIP:."""
        self._connected = False
        self._esp32.set_grip_callback(None)

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
        """Envoie une commande pince via ESP32_Link (préfixe GRIP:)."""
        if not self._connected:
            print(f"[PINCE] Non connectée -- commande '{sub_cmd}' ignorée.")
            return
        self._esp32._write_serial(f"GRIP:{sub_cmd}\n")
        print(f"[PINCE-TX] GRIP:{sub_cmd}")

    def _parse_grip_line(self, payload: str):
        """Appelé par ESP32_Link pour chaque ligne GRIP:<payload> reçue de l'ESP32."""
        print(f"[PINCE-RX] GRIP:{payload}")
        if payload == "READY":
            self._ev_ready.set()
        elif payload == "OPEN_DONE":
            self._ev_open_done.set()
        elif payload == "OBJECT_CAUGHT":
            self._ev_caught.set()
        elif payload in ("TIMEOUT_CALIB", "TIMEOUT_CLOSE"):
            self._ev_timeout.set()
