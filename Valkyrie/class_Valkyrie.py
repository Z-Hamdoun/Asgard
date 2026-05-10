import sys, os, math, time, threading
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

        # Parametres de la mission
        self.alt_quadrillage = 5.0
        self.pas_quadrillage = 2.0  # m entre les bandes
        self.taille_zone = 20.0     # taille totale du carré
        
        self._is_loitering = False
    
    # =========================================================================
    # LECTURE DE LA CONFIGURATION (VENANT DE VALHALLA VIA ESP32)
    # =========================================================================
    def load_config(self, config_dict: dict) -> bool:
        """
        Extrait les paramètres de la mission depuis le dictionnaire JSON
        et les stocke comme attributs de la classe.
        """
        if not config_dict:
            print("[VALKYRIE] Erreur : Dictionnaire de configuration vide.")
            return False
            
        print(f"[VALKYRIE] Chargement des paramètres de mission : {config_dict}")
        
        self.alt_quadrillage = config_dict.get("alt_quadrillage", 5.0)
        self.pas_quadrillage = config_dict.get("pas_quadrillage", 2.0)
        self.taille_zone = config_dict.get("taille_zone", 20.0)
            
        return True
    
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

    def executer_quadrillage(self) -> bool:
        """Effectue un quadrillage sous forme de spirale, de centre la Position GPS actuelle.

        Returns:
            bool: resultat de l'operation
        """
        print(f"\n[VALKYRIE] Début du quadrillage (Spirale).")
        
        print("[VALKYRIE] Acquisition de la position GPS de départ...")
        lat_depart, lon_depart, _, _ = self.position()
        
        while math.isnan(lat_depart) or math.isnan(lon_depart):
            time.sleep(0.1)
            lat_depart, lon_depart, _, _ = self.position()
            
        
        offsets = spirale(taille_spirale=self.taille_zone, pas=self.pas_quadrillage)
        
        point_actuel = 1
        total_points = len(offsets)
        
        for d_north, d_east in offsets:
            target_lat, target_lon = conv_cart_to_geo((lat_depart, lon_depart), (d_north, d_east))
            
            print(f"[VALKYRIE] -> Navigation Point {point_actuel}/{total_points}")
            self.goto(target_lat, target_lon, self.alt_quadrillage)
            
            while True:
                if self.fin_mission: return False
                    
                # Scan visuel
                dx, dy, dz, info, frame = self.camera.analyse(affichage=False) 
                
                # Cible trouvee
                if info is not None:
                    print("\n==================================================")
                    print(f"VALKYRIE] CIBLE ARUCO DÉTECTÉE (ID: {info}) !")
                    print("==================================================")
                    
                    # Passage en loiter
                    #
                    # NOTE TO SELF : N OUBLIE SURTOUT PAS D AJOUTER RC 3 1500
                    #
                    for _ in range(5):
                        if self.change_mode("LOITER"):
                            self._is_loitering = True
                            self._rc_thread = threading.Thread(target=self._rc_override_loop, daemon=True)
                            self._rc_thread.start()
                            return True

                # VÉRIFICATION DISTANCE
                current_lat, current_lon, _, _ = self.position()
                
                if not math.isnan(current_lat) and not math.isnan(current_lon):
                    dist = geodesic((current_lat, current_lon), (target_lat, target_lon)).meters
                    if dist < 1.5:
                        break
                        
                time.sleep(0.05) # 20 Hz, NOTE: a revoir
                
            point_actuel += 1

        print("\n[VALKYRIE] Quadrillage terminé. Cible non trouvée.")
        return False
    
    def precision_loiter_and_land(self) -> bool:
        """
        Precision loiter jusqu'a ce que la cible soit centree, puis precision LAND !!!
        """
        print("[VALKYRIE] Début du Precision Loiter...")
        
        # Phase 1 : Centrage en LOITER (On attend d'être stable)
        target_locked_frames = 0
        
        while True:
            if getattr(self, 'fin_mission', False): 
                self._is_loitering = False
                if self._rc_thread: self._rc_thread.join(timeout=1.0)
                return False
            dx, dy, dz, info, frame = self.camera.analyse(affichage=False)
            
            if info is not None:
                # Precision loiter
                self.send_landing_target(dx, dy, dz)
                target_locked_frames += 1
                
                # Si on l'a vu pendant environ 3s (~30 frames à 20Hz)
                if target_locked_frames > 60:
                    self._is_loitering = False
                    print("[VALKYRIE] Centré ! Debut de descente (LAND)...")
                    self.change_mode("LAND")
                    self._is_loitering = False
                    if self._rc_thread:
                        self._rc_thread.join(timeout=1.0) # On attend que le thread meure proprement
                    break
            else:
                # Si on le perd de vue, on tolère quelques frames avant de reset
                target_locked_frames = max(0, target_locked_frames - 1)
                
            time.sleep(0.05)
            
        # Phase 2 : Descente finale en mode LAND
        while True:
            if self.fin_mission: return False
            
            dx, dy, dz, info, frame = self.camera.analyse(affichage=False)
            
            if info is not None:
                self.send_landing_target(dx, dy, dz)
                
            # Quand les moteurs sont coupés, l'atterrissage est terminé
            if self.motors_disarmed():
                print("[VALKYRIE] Pose sur l'aruco avec succes!")
                return True
                
            time.sleep(0.05)
    
    
    # Utilitaire 
    def _rc_override_loop(self):
        """
        Thread activé dynamiquement uniquement pendant le Precision Loiter.
        Maintient les gaz à 1500. Se termine proprement quand _is_loitering passe à False.
        """
        print("[VALKYRIE] Thread RC Override DÉMARRÉ.")
        
        while self._is_loitering and not getattr(self, 'fin_mission', False):
            # On bloque les gaz à 1500 pour éviter la chute en LOITER, le reste (0) est libre
            self.master.mav.rc_channels_override_send(
                self.master.target_system, self.master.target_component,
                0, 0, 1500, 0,
                0, 0, 0, 2000
            )
            time.sleep(0.5) # Boucle à 2Hz
            
        # Quand on sort de la boucle (_is_loitering = False), on libère la radio
        print("[VALKYRIE] Libération de la radio (Thread RC Override ARRÊTÉ).")
        self.master.mav.rc_channels_override_send(
            self.master.target_system, self.master.target_component,
            0, 0, 0, 0, 0, 0, 0, 0
        )