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

    def wait_goto_gps(self, radius_acceptance: float = 2.0) -> bool:
        """
        Attend de recevoir un STATUSTEXT contenant les coordonnées de la cible,
        puis effectue un GOTO vers ce point et attend d'y être arrivé.
        """
        print("[Valhalla] En attente d'un point GPS depuis la carte Web...")
        lat_dest, lon_dest, alt_dest = None, None, None
        
        # Boucle d'attente des coordonnees
        while lat_dest is None:
            if self.fin_mission:
                return False
                
            # On ecoute les messages STATUSTEXT venant de la GCS
            m = self.get_msg("STATUSTEXT")
            
            if m and m.text.startswith("valhalla,"):
                try:
                    # On s'attend a un format : "valhalla,lat,lon,alt"
                    parts = m.text.split(',')
                    lat_dest = float(parts[1])
                    lon_dest = float(parts[2])
                    alt_dest = float(parts[3])
                except (IndexError, ValueError):
                    print(f"[Valhalla] Erreur de lecture des coordonnées : {m.text}")
                    
            time.sleep(0.1)
            
        print(f"[Valhalla] Cible reçue ! -> Lat: {lat_dest}, Lon: {lon_dest}, Alt: {alt_dest}m")
        
        # GOTO
        self.goto(lat_dest, lon_dest, alt_dest)
        
        # Envoi d'un message a Valkyrie une fois proche
        
        # Attente de l'arrivee
        print("[Valhalla] En route vers la destination...")
        arrived = self.wait_proximity(lat_dest, lon_dest, alt_dest, radius_acceptance, timeout=None)
        
        
        if not arrived or self.fin_mission:
            print("[Valhalla] Échec du GOTO ou mission annulée en vol.")
            return False
            
        print("[Valhalla] Destination atteinte ! Maintien de la position.")
        self.send_cgm(CGM.VALHALLA_POINT_ATTEINT)
        
        return True