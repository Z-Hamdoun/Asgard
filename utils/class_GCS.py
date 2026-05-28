import time
import queue as _queue
from pymavlink import mavutil
from pymavlink_code.class_MAVLinCS import MAVLinCS
import pymavlink_code.code_de_gestion_de_missions as CGM


def _cgm_category(name: str) -> str:
    n = name.upper()
    if "ESP32"   in n: return "ESP32"
    if "CONFIG"  in n: return "CONFIG"
    if "TAKEOFF" in n or "LAND" in n or "ARM" in n: return "FLIGHT"
    if "TARGET"  in n or "QUAD" in n: return "MISSION"
    if "MISSION" in n: return "MISSION"
    if "MODE"    in n: return "MODE"
    return "SYSTEM"


_LEVEL_LABELS = {
    CGM.Level.Sucesses: "SUCCESS",
    CGM.Level.Message:  "INFO",
    CGM.Level.Warning:  "WARN",
    CGM.Level.Failure:  "FAIL",
    CGM.Level.Critical: "CRIT",
}


def _format_cgm_event(cgm: CGM.CGM) -> dict:
    return {
        "type":            "status",
        "command":         "cgm_event",
        "source":          "GCS",
        "cgm_value":       cgm.value,
        "cgm_level":       _LEVEL_LABELS.get(cgm.level, "???"),
        "cgm_sender":      (cgm.potential_sender or "SYSTEM").upper(),
        "cgm_category":    _cgm_category(cgm.name),
        "cgm_description": cgm.short_description_str,
    }


class GroundStation:
    """
    Orchestrateur radio pour ASGARD.
    """
    
    def __init__(self, use_simu: bool = False):
        print("[GCS] Initialisation de l'antenne radio...")

        addr_valhalla = "0.0.0.0:14554"  # ATTENTION UDP

        print(f"[GCS] Tentative de connexion à Valhalla sur {addr_valhalla}")
        self.valhalla = MAVLinCS(
            address=addr_valhalla,
            target_system=1,
            timeout_heartbeat=10,
        )
        print("[GCS] Connexion MAVLink (UDP) établie avec succès.")

        # File thread-safe alimentée par le hook MAVLinCS - drainée par app.py
        self.cgm_event_queue: _queue.Queue = _queue.Queue()
        self.valhalla._cgm_hook = lambda cgm: self.cgm_event_queue.put(_format_cgm_event(cgm))

    # ==========================================
    # COMMANDES RADIO DESCENDANTES (PC -> VALHALLA)
    # ==========================================

    def lancer_mission(self, num: int = 1):
        """Envoie l'ordre de lancement de mission à Valhalla selon le numéro choisi."""
        cgm_map = {
            1: CGM.PC_DEMANDE_MISSION_1_VALHALLA,
            2: CGM.PC_DEMANDE_MISSION_2_VALHALLA,
            3: CGM.PC_DEMANDE_MISSION_3_VALHALLA,
            4: CGM.PC_DEMANDE_MISSION_4_VALHALLA,
            5: CGM.PC_DEMANDE_MISSION_5_VALHALLA,
        }
        cgm = cgm_map.get(num, CGM.PC_DEMANDE_MISSION_1_VALHALLA)
        print(f"[GCS-RADIO] Envoi mission {num} ({cgm.name}) à Valhalla...")
        self.valhalla.send_cgm(cgm)

    def envoyer_goto_gps(self, lat: float, lon: float, alt: float):
        """
        Envoie des coordonnées GPS cibles via un message STATUSTEXT.
        Valhalla les réceptionnera avec self.get_msg("STATUSTEXT").
        """
        # Format string reconnu par le script de Valhalla : "valhalla,lat,lon,alt"
        msg_text = f"valhalla,{lat},{lon},{alt}"
        
        print(f"[GCS-RADIO] Envoi GOTO à Valhalla -> Lat: {lat}, Lon: {lon}, Alt: {alt}")
        self.valhalla.send_statustext(msg_text, severity=7)

    def arret_urgence(self):
        """Force le désarmement immédiat de Valhalla (et relai vers Valkyrie via watcher Valhalla)."""
        print("[GCS-RADIO] !!! ARRÊT D'URGENCE ENVOYÉ À VALHALLA !!!")
        self.valhalla.send_cgm(CGM.PC_A_DISARM_FORCE_VALHALLA)
        self.valhalla.disarm(force=True)

    def atterrissage_urgence(self):
        """Ordonne l'atterrissage d'urgence de Valhalla (RTL + relai vers Valkyrie)."""
        print("[GCS-RADIO] !!! ATTERRISSAGE D'URGENCE ENVOYÉ À VALHALLA !!!")
        self.valhalla.send_cgm(CGM.PC_URGENCY_LANDING_VALHALLA)

    def force_rtl(self):
        """Force Valhalla à rentrer à la base, sans lui couper les moteurs."""
        self.valhalla.change_mode("RTL")
        print("[GCS-RADIO] RTL forcé envoyé à Valhalla.")
    
    def connect_valhalla(self):
        """Tente de connecter Valhalla au Dashboard.
        """
        print("[GCS-RADIO] Demande de configuer Valhalla.")
        cgm = CGM.PC_CONFIGURE_VALHALLA
        self.valhalla.send_cgm(cgm)

    def calibrer_pince(self):
        """Ordonne la calibration (homing) de la pince Valkyrie (relayé par Valhalla via ESP-NOW)."""
        print("[GCS-RADIO] Calibration pince Valkyrie.")
        self.valhalla.send_cgm(CGM.PC_CALIB_GRIPPER_VALKYRIE)

    def ouvrir_pince(self):
        """Ordonne l'ouverture manuelle de la pince Valkyrie (relayé par Valhalla via ESP-NOW)."""
        print("[GCS-RADIO] Ouverture pince Valkyrie.")
        self.valhalla.send_cgm(CGM.PC_OPEN_GRIPPER_VALKYRIE)

    def fermer_pince(self):
        """Ordonne la fermeture manuelle de la pince Valkyrie (relayé par Valhalla via ESP-NOW)."""
        print("[GCS-RADIO] Fermeture pince Valkyrie.")
        self.valhalla.send_cgm(CGM.PC_CLOSE_GRIPPER_VALKYRIE)

    def close(self):
        """Coupe proprement la connexion MAVLink."""
        print("[GCS] Fermeture du port MAVLink.")
        if self.valhalla:
            self.valhalla.close()