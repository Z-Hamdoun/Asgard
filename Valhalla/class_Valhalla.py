import sys
import os
import time
from pymavlink import mavutil
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
import pymavlink_code.code_de_gestion_de_missions as CGM

from class_Drone import Drone


class Valhalla(Drone):
    def __init__(self, address, source_system=255, source_component=mavutil.mavlink.MAV_COMP_ID_MISSIONPLANNER, target_system=None, baud=57600, timeout_heartbeat=None, send_automatic_timesync=True, timesync_delay=3, send_automatic_home_request=True, home_request_delay=3, sysid_to_request_home=None, pos_rate=4, dialect="ardupilotmega", logger = ..., camera_topic="/world/iris_runway/model/iris_with_gimbal/model/gimbal/link/pitch_link/sensor/camera/image"):
        super().__init__(address, source_system, source_component, target_system, baud, timeout_heartbeat, send_automatic_timesync, timesync_delay, send_automatic_home_request, home_request_delay, sysid_to_request_home, pos_rate, dialect, logger, camera_topic)
    
    
    def takeoff_pc(self, altitude) -> bool:
        """
        Attend le signal du PC pour s'armer et décoller.
        """
        
        # Attente ordres
        while True:
            if self.fin_mission: 
                return False
            if self.check_cgm(CGM.PC_DEMANDE_TAKEOFF_VALHALLA):
                self.delete_cgm(CGM.PC_DEMANDE_TAKEOFF_VALHALLA)
                break
            time.sleep(0.05)
        
        # Changement de mode
        for _ in range(5):
            if self.change_mode("GUIDED"):
                mode_changed = True
                break
            time.sleep(0.5)
        
        if not mode_changed:
            self.send_cgm(CGM.VALHALLA_MODE_CHANGE_FAIL)
            return False

        # Tentative d'armement
        for _ in range(5):
            if self.arm():
                armed = True
                break
            time.sleep(1)
        
        # Echech armement
        if not armed:
            self.send_cgm(CGM.VALHALLA_TAKEOFF_FAIL)
            return False

        # Tentative takeoff
        for _ in range(5):
            if self.takeoff(altitude):
                took_off = True
                break
            time.sleep(1)
        
        # Echec takeoff
        if not took_off:
            self.send_cgm(CGM.VALHALLA_TAKEOFF_FAIL)
            return False
        
        # Success
        self.send_cgm(CGM.VALHALLA_TOOKOFF)
        return True

    def execute_goto_from_config(self, radius_acceptance: float = 2.0) -> bool:
        """
        Effectue un GOTO en utilisant les coordonnées sauvegardées dans le fichier config
        """
        # Vérification que la configuration a bien été attachée au drone
        if not hasattr(self, 'config') or not self.config:
            print("[Valhalla] Erreur : Aucune configuration (self.config) n'a été attachée au drone.")
            return False

        # Lecture des coordonnées depuis l'attribut config
        lat_dest = self.config.get("lat_mission")
        lon_dest = self.config.get("lng_mission")
        alt_dest = self.config.get("alt_quadrillage", 10.0)

        if lat_dest is None or lon_dest is None:
            print("[Valhalla] Erreur : Coordonnées GPS absentes de la configuration.")
            self.send_cgm(CGM.VALHALLA_NO_TARGET_FOUND)
            return False

        print(f"[Valhalla] Cible chargée depuis self.config -> Lat: {lat_dest}, Lon: {lon_dest}, Alt: {alt_dest}m")
        
        # GOTO
        self.goto(lat_dest, lon_dest, alt_dest)
        
        # Attente de l'arrivée
        print("[Valhalla] En route vers la destination...")
        arrived = self.wait_proximity(lat_dest, lon_dest, alt_dest, radius_acceptance, timeout=None)
        
        if arrived == False:
            print("[Valhalla] Échec du GOTO")
            return False
            
        print("[Valhalla] Destination atteinte ! Maintien de la position.")
        self.send_cgm(CGM.VALHALLA_POINT_ATTEINT)
        
        return True

    def land_and_wait_valkyrie(self):
        # Envoi message vers valhalla pour qu'il commence sa mission (VIA ESP32)
        # A implementer apres ...
        
        # Atterissage
        for _ in range(5):
            if self.land():
                self.send_cgm(CGM.VALHALLA_LANDING)
                break
            time.sleep(1)
        
        while True:
            if self.fin_mission: 
                return False
            
            # Ici valhalla attend le signal de valkyrie (VIA ESP32)
            # Quand valkyrie lance son signal, valhalla transmet sa position GPS en 10Hz pour que valkyrie
            # passe en follow
            
            time.sleep(0.05)