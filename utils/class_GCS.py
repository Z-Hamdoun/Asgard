import threading
import time
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
from Valhalla.src.class_Valhalla import Valhalla 
import pymavlink_code.code_de_gestion_de_missions as CGM


class GroundStation:
    """Orchestrateur Radio de la mission ASGARD"""
    
    def __init__(self, addr_valhalla: str, baudrate_valhalla: int = 57600):
        print("[GCS] Initialisation de l'antenne radio...")
        
        # Instanciation de la connexion radio MAVLink vers Valhalla
        self.valhalla = Valhalla(
            system_type="pc",
            fc_adress=addr_valhalla,
            baudrate=baudrate_valhalla
        )
        # Plus tard, on ajoutera self.valkyrie ici !
        
        print("[GCS] Connecté à Valhalla.")

    # ==========================================
    # COMMANDES DESCENDANTES (PC -> DRONE)
    # ==========================================
    def lancer_mission_valhalla(self):
        """Déclenche la séquence de décollage de Valhalla."""
        print("[GCS] Envoi de l'ordre de décollage (CGM 208)...")
        # On envoie le CGM correspondant à PC_DEMANDE_TAKEOFF_VALHALLA
        self.valhalla.send_named_value_int(CGM.PC_DEMANDE_TAKEOFF_VALHALLA.value)

    def envoyer_goto_valhalla(self, lat: float, lon: float, alt: float = 5.0):
        """Envoie des coordonnées GPS cibles à Valhalla."""
        print(f"[GCS] Ordre GOTO envoyé vers {lat}, {lon} à {alt}m.")
        # On utilise un Statustext pour envoyer de la data pure (les coordonnées)
        self.valhalla.send_statustext(f"valhalla,{lat},{lon},{alt}", severity=7)

    def arret_urgence_valhalla(self):
        """Désarme les moteurs de Valhalla immédiatement."""
        print("[GCS] ARRÊT D'URGENCE VALHALLA !")
        self.valhalla.send_named_value_int(CGM.PC_A_DISARM_FORCE_VALHALLA.value)

    # ==========================================
    # FERMETURE
    # ==========================================
    def close(self):
        print("[GCS] Fermeture des connexions radio.")
        if self.valhalla:
            self.valhalla.close()