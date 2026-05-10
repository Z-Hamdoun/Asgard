import sys
import os
import time
from pymavlink import mavutil
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
import pymavlink_code.code_de_gestion_de_missions as CGM
from utils.class_Logger import Logger
from Valkyrie.vision.class_Camera import Camera

# Fonctions quadrillage
from geopy.distance import geodesic
from utils.geopy_fct import conv_cart_to_geo
from utils.spirale import spirale

from class_Drone import Drone


class Valkyrie(Drone):
    def __init__(self, address, source_system=255, source_component=mavutil.mavlink.MAV_COMP_ID_MISSIONPLANNER, target_system=None, baud=57600, timeout_heartbeat=None, send_automatic_timesync=True, timesync_delay=3, send_automatic_home_request=True, home_request_delay=3, sysid_to_request_home=None, pos_rate=4, dialect="ardupilotmega", logger = Logger(), camera_topic="/world/iris_runway/model/iris_with_gimbal/model/gimbal/link/pitch_link/sensor/camera/image"):
        super().__init__(address, source_system, source_component, target_system, baud, timeout_heartbeat, send_automatic_timesync, timesync_delay, send_automatic_home_request, home_request_delay, sysid_to_request_home, pos_rate, dialect, logger, camera_topic)
    
        self.camera = Camera(simulation=None)
    
    def takeoff_autonome(self, altitude) -> bool:
        """
        Attend le signal du PC pour s'armer et décoller.
        """
        for _ in range(5):
            if self.change_mode("GUIDED"):
                mode_changed = True
                break
            time.sleep(0.5)
        
        if not mode_changed:
            self.send_cgm(CGM.VALKYRIE_MODE_CHANGE_FAIL)
            return False

        # Tentative d'armement
        for _ in range(5):
            if self.arm():
                armed = True
                break
            time.sleep(1)
        
        # Echech armement
        if not armed:
            self.send_cgm(CGM.VALKYRIE_TAKEOFF_FAIL)
            return False

        # Tentative takeoff
        for _ in range(5):
            if self.takeoff(altitude):
                took_off = True
                break
            time.sleep(1)
        
        # Echec takeoff
        if not took_off:
            self.send_cgm(CGM.VALKYRIE_TAKEOFF_FAIL)
            return False
        
        # Success
        self.send_cgm(CGM.VALKYRIE_TOOKOFF)
        return True

    def executer_quadrillage(self, lat_center: float, lon_center: float, altitude: float, step_size=2.0, taille_zone=20.0) -> bool:
        """
        Exécute la trajectoire de recherche tout en scannant la caméra à 20Hz.
        S'arrête et passe en LOITER dès que la cible est détectée.
        
        Args:
            step_size: Distance entre les bandes de recherche en mètres.
            taille_zone: La largeur totale de la zone à couvrir en mètres.
        Returns:
            True si l'ArUco est trouvé, False sinon.
        """
        print(f"\n[VALKYRIE] Début du quadrillage (Spirale). Altitude: {altitude}m, Pas: {step_size}m")
        
        # Waypoints
        offsets = spirale(taille_spirale=taille_zone, pas=step_size)
        
        point_actuel = 1
        total_points = len(offsets)
        
        for d_north, d_east in offsets:
            
            # Conversion en coordonnees geographiques
            target_lat, target_lon = conv_cart_to_geo((lat_center, lon_center), (d_north, d_east))
            
            print(f"[VALKYRIE] Navigation vers le Point {point_actuel}/{total_points}")
            
            # Envoi de la commande de déplacement
            self.goto(target_lat, target_lon, altitude)
            
            # --- BOUCLE DE VÉRIFICATION ACTIVE ---
            while True:
                # A. SCAN VISUEL
                dx, dy, dz, info, frame = self.camera.analyse(affichage=False) 
                
                if info is not None:
                    print("\n==================================================")
                    print("[VALKYRIE] CIBLE ARUCO DÉTECTÉE EN VOL !")
                    print("==================================================")
                    self.change_mode("LOITER")
                    return True

                # VÉRIFICATION DE L'AVANCÉE GPS
                msg = self.get_msg("GLOBAL_POSITION_INT")
                if msg:
                    current_lat = msg.lat / 1e7
                    current_lon = msg.lon / 1e7
                    
                    # Utilisation directe de GeoPy pour une précision redoutable
                    dist = geodesic((current_lat, current_lon), (target_lat, target_lon)).meters
                    
                    # Si on est à moins de 2m du point visé, on passe au point suivant
                    if dist < 2:
                        break
                        
                time.sleep(0.05)
                
            point_actuel += 1

        print("\n[FAIL][VALKYRIE] Quadrillage complet terminé. Cible non trouvée.")
        return False
    