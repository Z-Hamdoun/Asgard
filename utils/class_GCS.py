import time
import math
import queue as _queue
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

        addr_valhalla = "127.0.0.1:14556"
        addr_valkyrie = "127.0.0.1:14557"

        print(f"[GCS] Connexion Valhalla sur {addr_valhalla}")
        self.valhalla = MAVLinCS(
            address=addr_valhalla,
            target_system=1,
            timeout_heartbeat=10,
        )
        print(f"[GCS] Connexion Valkyrie sur {addr_valkyrie}")
        self.valkyrie = MAVLinCS(
            address=addr_valkyrie,
            target_system=2,
            timeout_heartbeat=10,
        )
        print("[GCS] Connexions MAVLink (UDP) établies avec succès.")

        # File thread-safe alimentée par les hooks MAVLinCS - drainée par app.py
        self.cgm_event_queue: _queue.Queue = _queue.Queue()
        self.valkyrie._cgm_hook = lambda cgm: self.cgm_event_queue.put(_format_cgm_event(cgm))

        # Hook Valhalla : enfile le CGM dans la queue dashboard uniquement.
        # Toutes les commandes vers Valkyrie partent directement du GCS (jamais via Valhalla).
        self.valhalla._cgm_hook = lambda cgm: self.cgm_event_queue.put(_format_cgm_event(cgm))

    # ==========================================
    # COMMANDES RADIO DESCENDANTES (PC -> VALHALLA)
    # ==========================================

    def lancer_mission(self, num: int = 1):
        """Envoie l'ordre de lancement de mission à Valhalla ET Valkyrie simultanément."""
        cgm_map_v = {
            1: CGM.PC_DEMANDE_MISSION_1_VALHALLA,
            2: CGM.PC_DEMANDE_MISSION_2_VALHALLA,
            3: CGM.PC_DEMANDE_MISSION_3_VALHALLA,
            4: CGM.PC_DEMANDE_MISSION_4_VALHALLA,
            5: CGM.PC_DEMANDE_MISSION_5_VALHALLA,
        }
        cgm_map_vk = {
            1: CGM.PC_DEMANDE_MISSION_1_VALKYRIE,
            2: CGM.PC_DEMANDE_MISSION_2_VALKYRIE,
            3: CGM.PC_DEMANDE_MISSION_3_VALKYRIE,
            4: CGM.PC_DEMANDE_MISSION_4_VALKYRIE,
            5: CGM.PC_DEMANDE_MISSION_5_VALKYRIE,
        }
        cgm_v  = cgm_map_v.get(num,  CGM.PC_DEMANDE_MISSION_1_VALHALLA)
        cgm_vk = cgm_map_vk.get(num, CGM.PC_DEMANDE_MISSION_1_VALKYRIE)
        print(f"[GCS] Lancement mission {num} → Valhalla ({cgm_v.name}) + Valkyrie ({cgm_vk.name}).")
        self.valhalla.send_cgm(cgm_v)
        self.valkyrie.send_cgm(cgm_vk)

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
        """Force le désarmement immédiat de Valhalla ET Valkyrie simultanément."""
        print("[GCS-RADIO] !!! ARRÊT D'URGENCE ENVOYÉ AUX DEUX DRONES !!!")
        self.valhalla.send_cgm(CGM.PC_A_DISARM_FORCE_VALHALLA)
        self.valhalla.disarm(force=True)
        self.valkyrie.send_cgm(CGM.PC_A_DISARM_FORCE_VALKYRIE)
        self.valkyrie.disarm(force=True)

    def atterrissage_urgence(self):
        """Ordonne l'atterrissage d'urgence (LAND) des deux drones simultanément."""
        print("[GCS-RADIO] !!! ATTERRISSAGE D'URGENCE ENVOYÉ AUX DEUX DRONES !!!")
        self.valhalla.send_cgm(CGM.PC_URGENCY_LANDING_VALHALLA)
        self.valkyrie.send_cgm(CGM.PC_URGENCY_LANDING_VALKYRIE)

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

    def configurer_valkyrie(self):
        """Ordonne à Valkyrie de se connecter au Dashboard (radio directe)."""
        print("[GCS-RADIO] Demande de connexion WiFi Valkyrie.")
        self.valkyrie.send_cgm(CGM.PC_CONFIGURE_VALKYRIE)

    def calibrer_pince(self):
        """Ordonne la calibration (homing) de la pince Valkyrie (radio directe)."""
        print("[GCS-RADIO] Calibration pince Valkyrie.")
        self.valkyrie.send_cgm(CGM.PC_CALIB_GRIPPER_VALKYRIE)

    def ouvrir_pince(self):
        """Ordonne l'ouverture manuelle de la pince Valkyrie (radio directe)."""
        print("[GCS-RADIO] Ouverture pince Valkyrie.")
        self.valkyrie.send_cgm(CGM.PC_OPEN_GRIPPER_VALKYRIE)

    def fermer_pince(self):
        """Ordonne la fermeture manuelle de la pince Valkyrie (radio directe)."""
        print("[GCS-RADIO] Fermeture pince Valkyrie.")
        self.valkyrie.send_cgm(CGM.PC_CLOSE_GRIPPER_VALKYRIE)

    def goto_valkyrie_au_dessus_valhalla(self, retries: int = 5,
                                         timeout_par_essai: float = 60.0,
                                         seuil_m: float = 2.5) -> bool:
        """
        Récupère le GPS de Valhalla puis envoie un goto à Valkyrie pour se positionner
        2m au-dessus. Réessaie jusqu'à `retries` fois si le drone n'arrive pas à temps.
        Met Valkyrie en LOITER une fois positionné.

        Returns:
            True si Valkyrie est positionné au-dessus de Valhalla, False sinon.
        """
        for tentative in range(retries):
            # Lire la position fraîche de Valhalla
            lat_v, lon_v, alt_v, _ = self.valhalla.position(source_system=1)
            if math.isnan(lat_v) or math.isnan(lon_v):
                print(f"[GCS] Tentative {tentative + 1}/{retries} : GPS Valhalla absent. Retry...")
                time.sleep(1.0)
                continue

            alt_cible = (alt_v if not math.isnan(alt_v) else 0.0) + 2.0
            print(f"[GCS] Tentative {tentative + 1}/{retries} : goto Valkyrie "
                  f"({lat_v:.6f}, {lon_v:.6f}) alt={alt_cible:.1f}m")
            self.valkyrie.goto(lat_v, lon_v, alt_cible)

            # Attente d'arrivée
            deadline = time.time() + timeout_par_essai
            while time.time() < deadline:
                lat_vk, lon_vk, _, _ = self.valkyrie.position()
                if not math.isnan(lat_vk) and not math.isnan(lon_vk):
                    dist = self.valkyrie.get_distance_with(lat_v, lon_v)
                    if not math.isnan(dist) and dist < seuil_m:
                        print(f"[GCS] Valkyrie au-dessus de Valhalla (dist={dist:.1f}m). LOITER.")
                        self.valkyrie.change_mode("LOITER")
                        return True
                # Rafraîchir la cible si Valhalla s'est déplacé
                lat_nv, lon_nv, alt_nv, _ = self.valhalla.position(source_system=1)
                if not math.isnan(lat_nv) and not math.isnan(lon_nv):
                    if abs(lat_nv - lat_v) > 1e-5 or abs(lon_nv - lon_v) > 1e-5:
                        lat_v, lon_v = lat_nv, lon_nv
                        if not math.isnan(alt_nv):
                            alt_cible = alt_nv + 2.0
                        self.valkyrie.goto(lat_v, lon_v, alt_cible)
                time.sleep(0.5)

            print(f"[GCS] Timeout tentative {tentative + 1}/{retries}.")

        print(f"[GCS] Impossible de positionner Valkyrie au-dessus de Valhalla après {retries} tentatives.")
        return False

    def lancer_mission_valkyrie(self, num: int = 1):
        """Envoie l'ordre de lancement de mission directement à Valkyrie via radio MAVLink."""
        cgm_map = {
            1: CGM.PC_DEMANDE_MISSION_1_VALKYRIE,
            2: CGM.PC_DEMANDE_MISSION_2_VALKYRIE,
            3: CGM.PC_DEMANDE_MISSION_3_VALKYRIE,
            4: CGM.PC_DEMANDE_MISSION_4_VALKYRIE,
            5: CGM.PC_DEMANDE_MISSION_5_VALKYRIE,
        }
        cgm = cgm_map.get(num, CGM.PC_DEMANDE_MISSION_1_VALKYRIE)
        print(f"[GCS-RADIO] Envoi mission {num} ({cgm.name}) à Valkyrie (radio directe)...")
        self.valkyrie.send_cgm(cgm)

    def arret_urgence_valkyrie(self):
        """Force le désarmement immédiat de Valkyrie (radio directe)."""
        print("[GCS-RADIO] !!! ARRÊT D'URGENCE ENVOYÉ À VALKYRIE !!!")
        self.valkyrie.send_cgm(CGM.PC_A_DISARM_FORCE_VALKYRIE)
        self.valkyrie.disarm(force=True)

    def atterrissage_urgence_valkyrie(self):
        """Ordonne l'atterrissage d'urgence de Valkyrie (radio directe)."""
        print("[GCS-RADIO] !!! ATTERRISSAGE D'URGENCE ENVOYÉ À VALKYRIE !!!")
        self.valkyrie.send_cgm(CGM.PC_URGENCY_LANDING_VALKYRIE)

    def close(self):
        """Coupe proprement les connexions MAVLink."""
        print("[GCS] Fermeture des ports MAVLink.")
        if self.valhalla:
            self.valhalla.close()
        if self.valkyrie:
            self.valkyrie.close()