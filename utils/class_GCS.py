import time
from pymavlink_code.class_MAVLinCS import MAVLinCS
import pymavlink_code.code_de_gestion_de_missions as CGM

class GroundStation:
    """
    Orchestrateur radio pour ASGARD.
    """
    
    def __init__(self, use_simu: bool = False):
        print("[GCS] Initialisation de l'antenne radio...")
        
        # Adresse locale UDP générée par MAVProxy
        addr_valhalla = "0.0.0.0:14550"

        # Connexion a Valhalla
        print(f"[GCS] Tentative de connexion à Valhalla sur {addr_valhalla}")
        self.valhalla = MAVLinCS(
            address=addr_valhalla,
            target_system=1, 
        )
        
        print("[GCS] Connexion MAVLink (UDP) établie avec succès.")

    # ==========================================
    # COMMANDES RADIO DESCENDANTES (PC -> VALHALLA)
    # ==========================================

    def lancer_mission(self):
        """Envoie l'ordre de décollage (Takeoff) à Valhalla."""
        cgm = CGM.PC_DEMANDE_TAKEOFF_VALHALLA
        print(f"[GCS-RADIO] Envoi ordre de mission ({cgm}) à Valhalla...")
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
        """Ordonne le désarmement immédiat de Valhalla."""
        code = CGM.PC_A_DISARM_FORCE_VALHALLA.value
        print("[GCS-RADIO] !!! ARRÊT D'URGENCE ENVOYÉ À VALHALLA !!!")
        self.valhalla.send_named_value_int(code)

    def force_rtl(self):
        """Force Valhalla à rentrer à la base, sans lui couper les moteurs."""
        self.valhalla.change_mode("RTL")
        print("[GCS-RADIO] RTL forcé envoyé à Valhalla.")

    def close(self):
        """Coupe proprement la connexion MAVLink."""
        print("[GCS] Fermeture du port MAVLink.")
        if self.valhalla:
            self.valhalla.close()