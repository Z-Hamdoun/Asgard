from __future__ import annotations
import sys, os, math, time, threading
from typing import TYPE_CHECKING
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

if TYPE_CHECKING:
    from Communication.class_ESP32_Link import ESP32_Link

# Seuils failsafe (à 20 Hz = 0.05s par frame)
_MAX_LOST_FRAMES_LOITER = 100  # 5s - cible perdue en loiter --> requadrillage
_MAX_LOST_FRAMES_LAND   = 40   # 2s - cible perdue en land --> remonter


class Valkyrie(Drone):
    def __init__(self, address, source_system=255, source_component=mavutil.mavlink.MAV_COMP_ID_MISSIONPLANNER, target_system=None, baud=57600, timeout_heartbeat=None, send_automatic_timesync=True, timesync_delay=3, send_automatic_home_request=True, home_request_delay=3, sysid_to_request_home=None, pos_rate=4, dialect="ardupilotmega", logger = Logger(), camera_topic="/world/iris_runway/model/drone1/model/gimbal/link/pitch_link/sensor/camera/image"):
        super().__init__(address, source_system, source_component, target_system, baud, timeout_heartbeat, send_automatic_timesync, timesync_delay, send_automatic_home_request, home_request_delay, sysid_to_request_home, pos_rate, dialect, logger, camera_topic)

        self.camera = Camera(simulation='SITL', camera_topic="/world/iris_runway/model/drone1/model/gimbal/link/pitch_link/sensor/camera/image")

        # Parametres de la mission
        self.alt_quadrillage = 5.0
        self.pas_quadrillage = 2.0
        self.taille_zone = 20.0

        # Lien ESP32 pour relayer les CGMs vers Valhalla (pas de liaison radio directe)
        self._esp32_link: ESP32_Link | None = None

        # Gestion du thread RC
        self._precision_active = False
        self._rc_throttle_pwm = 0
        self._rc_thread = None

    def set_esp32_link(self, esp32: ESP32_Link):
        """Enregistre le lien ESP32 utilisé pour router les CGMs via Valhalla."""
        self._esp32_link = esp32

    def send_cgm(self, cgm: CGM.CGM):
        """
        Override : envoie le CGM via ESP32 -> Valhalla -> GCS.
        Fallback sur MAVLink si esp32_link non configuré.
        """
        if self._esp32_link is not None:
            self._esp32_link.send_cgm(cgm.value)
        else:
            super().send_cgm(cgm)

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

        print("[VALKYRIE] Chargement des paramètres de mission...")

        self.alt_quadrillage   = config_dict.get("alt_quadrillage", 5.0)
        self.pas_quadrillage   = config_dict.get("pas_quadrillage", 2.0)
        self.taille_zone       = config_dict.get("taille_quadrillage", 20.0)
        self.camera_resolution = config_dict.get("camera_resolution", [848, 480])
        self.square_pnp_size   = config_dict.get("square_pnp_size", 40)
        self.taille_aruco      = config_dict.get("taille_aruco", [40, 10])
        self.id_aruco          = config_dict.get("id_aruco", [1, 1])

        print(f"  alt={self.alt_quadrillage}m  pas={self.pas_quadrillage}m  "
              f"taille={self.taille_zone}m  aruco_id={self.id_aruco}")
        return True

    def takeoff_autonome(self, altitude) -> bool:
        """
        Attend le signal du PC pour s'armer et décoller.
        """
        mode_changed = False
        for _ in range(5):
            if self.change_mode("GUIDED"):
                mode_changed = True
                break
            time.sleep(3)

        if not mode_changed:
            self.send_cgm(CGM.VALKYRIE_MODE_CHANGE_FAIL)
            return False

        # Tentative d'armement
        armed = False
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
        took_off = False
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

                    self._rc_throttle_pwm = 1500 # Maintien d'altitude en Loiter
                    self._precision_active = True

                    self._rc_thread = threading.Thread(target=self._rc_override_loop, daemon=True)
                    self._rc_thread.start()
                    # Passage en loiter
                    #
                    # NOTE TO SELF : N OUBLIE SURTOUT PAS D AJOUTER RC 3 1500
                    #
                    for _ in range(5):
                        if self.change_mode("LOITER"):
                            return True
                    self._precision_active = False
                    return False

                # VÉRIFICATION DISTANCE
                current_lat, current_lon, _, _ = self.position()

                if not math.isnan(current_lat) and not math.isnan(current_lon):
                    dist = geodesic((current_lat, current_lon), (target_lat, target_lon)).meters
                    if dist < 1.5:
                        break

                time.sleep(0.05) # 20 Hz, NOTE: a revoir

            point_actuel += 1

        print("\n[VALKYRIE] Quadrillage terminé. Cible non trouvée.")
        self.return_to_launch()
        return False

    def precision_loiter_and_land(self) -> "bool | None":
        """
        Precision loiter jusqu'a ce que la cible soit centree, puis precision LAND.

        Returns:
            True  : atterrissage réussi
            False : fin_mission recu
            None  : cible perdue en LOITER --> requadrillage nécessaire
        """
        print("[VALKYRIE] Début du Precision Loiter...")

        while True:  # Boucle externe : LAND avorté --> retour en LOITER

            # -- Phase 1 : Centrage en LOITER ----------------------------------
            target_locked_frames = 0
            lost_frames_loiter   = 0

            while True:
                if getattr(self, 'fin_mission', False):
                    self._precision_active = False
                    if self._rc_thread:
                        self._rc_thread.join(timeout=1.0)
                    return False

                dx, dy, dz, info, _ = self.camera.analyse(affichage=False)

                if info is not None:
                    self.send_landing_target(dx, dy, dz)
                    target_locked_frames += 1
                    lost_frames_loiter    = 0

                    if target_locked_frames > 60:
                        print("[VALKYRIE] Centré ! Début de descente (LAND)...")
                        self._rc_throttle_pwm = 0
                        self.change_mode("LAND")
                        break
                else:
                    target_locked_frames = max(0, target_locked_frames - 1)
                    lost_frames_loiter  += 1

                    if lost_frames_loiter > _MAX_LOST_FRAMES_LOITER:
                        print("[VALKYRIE] Cible perdue en LOITER (5s) --> requadrillage.")
                        self._precision_active = False
                        self.change_mode("GUIDED")
                        if self._rc_thread:
                            self._rc_thread.join(timeout=1.0)
                        return None

                time.sleep(0.05)

            # -- Phase 2 : Descente en LAND -------------------------------------
            lost_frames_land = 0
            land_aborted     = False

            while True:
                if getattr(self, 'fin_mission', False):
                    self._precision_active = False
                    return False

                dx, dy, dz, info, _ = self.camera.analyse(affichage=False)

                if info is not None:
                    self.send_landing_target(dx, dy, dz)
                    lost_frames_land = 0
                else:
                    lost_frames_land += 1
                    if lost_frames_land > _MAX_LOST_FRAMES_LAND:
                        print("[VALKYRIE] Cible perdue en LAND (2s) --> remontée.")
                        land_aborted = True
                        break

                if self.motors_disarmed():
                    print("[VALKYRIE] Pose sur l'aruco avec succès !")
                    self._precision_active = False
                    if self._rc_thread:
                        self._rc_thread.join(timeout=1.0)
                    return True

                time.sleep(0.05)

            # -- Remontée et retour en LOITER -----------------------------------
            if land_aborted:
                print("[VALKYRIE] Remontée vers alt_quadrillage et retour en LOITER...")
                self.change_mode("GUIDED")
                lat, lon, _, _ = self.position()
                self.goto(lat, lon, self.alt_quadrillage)

                # Attendre d'être proche de l'altitude cible (max 15s)
                deadline = time.time() + 15.0
                while time.time() < deadline:
                    if getattr(self, 'fin_mission', False):
                        self._precision_active = False
                        return False
                    _, _, alt, _ = self.position()
                    if not math.isnan(alt) and alt >= self.alt_quadrillage - 1.0:
                        break
                    time.sleep(0.2)

                self._rc_throttle_pwm = 1500
                for _ in range(5):
                    if self.change_mode("LOITER"):
                        break
                # Retour phase 1 (outer while loop continue)


    # Utilitaire
    def _rc_override_loop(self):
        """
        Thread activé pendant le Precision Loiter et Precision land.
        """
        print("[VALKYRIE] Thread RC Override DÉMARRÉ.")

        while self._precision_active and not getattr(self, 'fin_mission', False):
            # On controle le gaz selon si le drone est en loiter ounon
            self.master.mav.rc_channels_override_send(
                self.master.target_system, self.master.target_component,
                0, 0, self._rc_throttle_pwm, 0,
                0, 0, 0, 2000
            )
            time.sleep(0.1) # Boucle à 10Hz

        # Quand on sort de la boucle et on libère la radio
        print("[VALKYRIE] Libération de la radio (Thread RC Override ARRÊTÉ).")
        self.master.mav.rc_channels_override_send(
            self.master.target_system, self.master.target_component,
            0, 0, 0, 0, 0, 0, 0, 0
        )
