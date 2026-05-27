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

# Seuils failsafe (secondes -- indépendants du FPS caméra)
_LOITER_LOCK_DURATION = 3.0   # s -- centrage requis avant de passer en LAND
_LOITER_LOST_TIMEOUT  = 5.0   # s -- cible perdue en LOITER --> requadrillage
_LAND_LOST_TIMEOUT    = 5.0   # s -- cible perdue en LAND --> remontée
_YAW_TOLERANCE_DEG    = 5.0   # ° -- tolérance d'alignement yaw
_ARUCO_CGM_INTERVAL   = 5.0   # s -- intervalle minimum entre deux CGMs ArUco du même type


class Valkyrie(Drone):
    def __init__(self, address, source_system=255, source_component=mavutil.mavlink.MAV_COMP_ID_MISSIONPLANNER, target_system=None, baud=57600, timeout_heartbeat=None, send_automatic_timesync=True, timesync_delay=3, send_automatic_home_request=True, home_request_delay=3, sysid_to_request_home=None, pos_rate=4, dialect="ardupilotmega", logger = Logger(), camera_topic="/world/iris_runway/model/drone1/model/gimbal/link/pitch_link/sensor/camera/image"):
        super().__init__(address, source_system, mavutil.mavlink.MAV_COMP_ID_ONBOARD_COMPUTER, target_system, baud, timeout_heartbeat, send_automatic_timesync, timesync_delay, send_automatic_home_request, home_request_delay, sysid_to_request_home, pos_rate, dialect, logger, camera_topic)

        self.camera = Camera(simulation='SITL', camera_topic="/world/iris_runway/model/drone1/model/gimbal/link/pitch_link/sensor/camera/image")

        # Parametres de la mission
        self.alt_quadrillage = 5.0
        self.pas_quadrillage = 2.0
        self.taille_zone = 20.0

        # Lien ESP32 pour relayer les CGMs vers Valhalla (pas de liaison radio directe)
        self._esp32_link: ESP32_Link | None = None

        # Offsets mécaniques (m, repère body FRD)
        self.cam_x_m  = 0.0   # camera : offset X par rapport au centre du drone
        self.cam_y_m  = 0.0   # camera : offset Y par rapport au centre du drone
        self.grip_x_m = 0.05   # pince  : offset X sur l'axe du nez (avant positif)

        # Gestion du thread RC
        self._precision_active = False
        self._rc_throttle_pwm = 0
        self._rc_yaw_pwm      = 0   # 0 = pas d'override (pilote/FC reprend le canal)
        self._rc_thread = None

        # Rate-limiting CGMs ArUco (évite le spam)
        self._last_outer_cgm = 0.0
        self._last_inner_cgm = 0.0

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

        # PLND_LAND_OFS_X (cm) : le centre du drone se pose grip_x_m derrière la cible,
        # ce qui amène la pince exactement sur la cible.
        land_ofs_cm = int(self.grip_x_m * 100)
        self.write_parameter("PLND_LAND_OFS_X", land_ofs_cm,
                             mavutil.mavlink.MAV_PARAM_TYPE_INT8)
        print(f"  cam_offset=({self.cam_x_m:.3f}, {self.cam_y_m:.3f})m  "
              f"grip_x={self.grip_x_m:.3f}m  PLND_LAND_OFS_X={land_ofs_cm}cm")

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

        if not armed:
            self.send_cgm(CGM.VALKYRIE_ARM_FAIL)
            return False

        self.send_cgm(CGM.VALKYRIE_ARMED)

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


    def executer_quadrillage(self, e_analyse: bool = False) -> bool:
        """Effectue un quadrillage sous forme de spirale, de centre la Position GPS actuelle.

        Args:
            e_analyse (bool): True = détection e-ArUco (inner+outer), False = analyse classique.

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
                scan = self.camera.analyse_e_aruco if e_analyse else self.camera.analyse
                dx, dy, dz, info, frame = scan(affichage=False)

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

    def precision_loiter_and_land(self, e_analyse: bool = False) -> "bool | None":
        """
        Precision loiter jusqu'a ce que la cible soit centree, puis precision LAND.

        Args:
            e_analyse (bool): True = détection e-ArUco (inner+outer), False = analyse classique.

        Returns:
            True  : atterrissage réussi
            False : fin_mission recu
            None  : cible perdue en LOITER --> requadrillage nécessaire
        """
        print("[VALKYRIE] Début du Precision Loiter...")
        scan = self.camera.analyse_e_aruco if e_analyse else self.camera.analyse

        while True:  # Boucle externe : LAND avorté --> retour en LOITER

            # -- Phase 1 : Centrage en LOITER ----------------------------------
            target_locked_since = None
            target_lost_since   = None

            while True:
                if getattr(self, 'fin_mission', False):
                    self._precision_active = False
                    if self._rc_thread:
                        self._rc_thread.join(timeout=1.0)
                    return False

                dx, dy, dz, info, _ = scan(affichage=False)
                now = time.time()

                if info is not None:
                    self._maybe_send_aruco_cgm(info)
                    self.send_landing_target(dx, dy, dz)
                    if target_locked_since is None:
                        target_locked_since = now
                    target_lost_since = None

                    elapsed = now - target_locked_since
                    print(f"[LOITER] centrage {elapsed:.1f}/{_LOITER_LOCK_DURATION:.0f}s", end="\r")

                    if elapsed >= _LOITER_LOCK_DURATION:
                        print()
                        print("[VALKYRIE] Centré ! Début de descente (LAND)...")
                        self.send_cgm(CGM.VALKYRIE_PRECISION_LAND_STARTING)
                        self._rc_throttle_pwm = 0
                        self.change_mode("LAND")
                        break
                else:
                    if target_lost_since is None:
                        target_lost_since = now
                    if now - target_lost_since >= 1.0:
                        target_locked_since = None

                    if now - target_lost_since >= _LOITER_LOST_TIMEOUT:
                        print(f"\n[VALKYRIE] Cible perdue en LOITER ({_LOITER_LOST_TIMEOUT:.0f}s) --> requadrillage.")
                        self.send_cgm(CGM.VALKYRIE_LOITER_LOST_TARGET)
                        self._precision_active = False
                        self.change_mode("GUIDED")
                        if self._rc_thread:
                            self._rc_thread.join(timeout=1.0)
                        return None

                time.sleep(0.05)

            # -- Phase 2 : Descente en LAND -------------------------------------
            land_lost_since = None
            land_aborted    = False

            while True:
                if getattr(self, 'fin_mission', False):
                    self._precision_active = False
                    return False

                dx, dy, dz, info, _ = scan(affichage=False)
                now = time.time()

                if info is not None:
                    self._maybe_send_aruco_cgm(info)
                    self.send_landing_target(dx, dy, dz)
                    land_lost_since = None
                else:
                    if land_lost_since is None:
                        land_lost_since = now
                    if now - land_lost_since >= _LAND_LOST_TIMEOUT:
                        print(f"[VALKYRIE] Cible perdue en LAND ({_LAND_LOST_TIMEOUT:.0f}s) --> remontée.")
                        self.send_cgm(CGM.VALKYRIE_LAND_ABORTED)
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


    def precision_loiter_and_land_gripper(self, e_analyse: bool = False) -> "bool | None":
        """
        Variante de precision_loiter_and_land avec :
          - correction de l'offset caméra sur send_landing_target
          - alignement yaw (nez vers la cible) avant de passer en LAND

        Returns:
            True  : atterrissage réussi
            False : fin_mission recu
            None  : cible perdue en LOITER --> requadrillage nécessaire
        """
        print("[VALKYRIE] Début du Precision Loiter (Gripper)...")
        scan = self.camera.analyse_e_aruco if e_analyse else self.camera.analyse

        while True:

            # -- Phase 1a : Centrage en LOITER ---------------------------------
            target_locked_since = None
            target_lost_since   = None

            while True:
                if getattr(self, 'fin_mission', False):
                    self._precision_active = False
                    if self._rc_thread:
                        self._rc_thread.join(timeout=1.0)
                    return False

                dx, dy, dz, info, _ = scan(affichage=False)
                now = time.time()

                if info is not None:
                    self._maybe_send_aruco_cgm(info)
                    dx_c = dx + self.cam_x_m
                    dy_c = dy + self.cam_y_m
                    self.send_landing_target(dx_c, dy_c, dz)
                    if target_locked_since is None:
                        target_locked_since = now
                    target_lost_since = None

                    elapsed = now - target_locked_since
                    print(f"[LOITER] centrage {elapsed:.1f}/{_LOITER_LOCK_DURATION:.0f}s", end="\r")

                    if elapsed >= _LOITER_LOCK_DURATION:
                        print()
                        print("[VALKYRIE] Centré ! Alignement yaw pince...")
                        self._align_yaw_to_target(dx_c, dy_c)
                        print("[VALKYRIE] Début de descente (LAND)...")
                        self.send_cgm(CGM.VALKYRIE_PRECISION_LAND_STARTING)
                        self._rc_throttle_pwm = 0
                        self.change_mode("LAND")
                        break
                else:
                    if target_lost_since is None:
                        target_lost_since = now
                    # Grâce de 1 s : une perte brève ne remet pas le timer à zéro
                    if now - target_lost_since >= 1.0:
                        target_locked_since = None

                    if now - target_lost_since >= _LOITER_LOST_TIMEOUT:
                        print(f"\n[VALKYRIE] Cible perdue en LOITER ({_LOITER_LOST_TIMEOUT:.0f}s) --> requadrillage.")
                        self.send_cgm(CGM.VALKYRIE_LOITER_LOST_TARGET)
                        self._precision_active = False
                        self.change_mode("GUIDED")
                        if self._rc_thread:
                            self._rc_thread.join(timeout=1.0)
                        return None

                time.sleep(0.05)

            # -- Phase 2 : Descente en LAND -------------------------------------
            land_lost_since = None
            land_aborted    = False

            while True:
                if getattr(self, 'fin_mission', False):
                    self._precision_active = False
                    return False

                dx, dy, dz, info, _ = scan(affichage=False)
                now = time.time()

                if info is not None:
                    self._maybe_send_aruco_cgm(info)
                    self.send_landing_target(dx + self.cam_x_m, dy + self.cam_y_m, dz)
                    land_lost_since = None
                else:
                    if land_lost_since is None:
                        land_lost_since = now
                    if now - land_lost_since >= _LAND_LOST_TIMEOUT:
                        print(f"[VALKYRIE] Cible perdue en LAND ({_LAND_LOST_TIMEOUT:.0f}s) --> remontée.")
                        self.send_cgm(CGM.VALKYRIE_LAND_ABORTED)
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

    # =========================================================================
    # CGMs ARUCO (rate-limited)
    # =========================================================================
    def _maybe_send_aruco_cgm(self, info) -> None:
        """Envoie un CGM de détection ArUco (inner ou outer) au plus toutes les
        _ARUCO_CGM_INTERVAL secondes pour éviter le spam."""
        now = time.time()
        if info == self.camera.inner_aruco_id:
            if now - self._last_inner_cgm >= _ARUCO_CGM_INTERVAL:
                self.send_cgm(CGM.VALKYRIE_INNER_ARUCO_DETECTED)
                self._last_inner_cgm = now
        elif info == self.camera.outer_aruco_id:
            if now - self._last_outer_cgm >= _ARUCO_CGM_INTERVAL:
                self.send_cgm(CGM.VALKYRIE_OUTER_ARUCO_DETECTED)
                self._last_outer_cgm = now

    # =========================================================================
    # ALIGNEMENT YAW (pince sur axe du nez)
    # =========================================================================
    def _align_yaw_to_target(self, dx: float, dy: float,
                              tolerance_deg: float = _YAW_TOLERANCE_DEG,
                              timeout: float = 10.0) -> bool:
        """
        Pivote le drone en LOITER pour aligner le nez (et la pince) vers la cible,
        via RC override sur le canal 4 (yaw).

        Aucun changement de mode : on reste en LOITER. Le thread _rc_override_loop
        déjà actif diffuse _rc_yaw_pwm à 10 Hz. À la fin (convergence ou timeout),
        _rc_yaw_pwm est remis à 0 --> le FC/pilote reprend le canal yaw, et LOITER
        gèle automatiquement le cap atteint.

        dx/dy en repère body FRD (x=avant, y=droite), déjà corrigés de l'offset caméra.
        Retourne True si convergé dans le timeout, False sinon.
        """
        angle_deg = math.degrees(math.atan2(dy, dx))

        if abs(angle_deg) < tolerance_deg:
            return True

        _, _, current_yaw_rad = self.angles()
        if math.isnan(current_yaw_rad):
            return False

        target_yaw_deg = (math.degrees(current_yaw_rad) + angle_deg) % 360

        # Sens de rotation : PWM > 1500 = CW, PWM < 1500 = CCW
        self._rc_yaw_pwm = 1600 if angle_deg >= 0 else 1400
        print(f"[VALKYRIE] Alignement yaw : rotation {angle_deg:+.1f}° --> cible {target_yaw_deg:.1f}°")

        deadline = time.time() + timeout
        try:
            while time.time() < deadline:
                if getattr(self, 'fin_mission', False):
                    return False
                _, _, yaw_rad = self.angles()
                if not math.isnan(yaw_rad):
                    yaw_deg = math.degrees(yaw_rad) % 360
                    error = abs((yaw_deg - target_yaw_deg + 180) % 360 - 180)
                    if error < tolerance_deg:
                        print(f"[VALKYRIE] Yaw aligné (erreur résiduelle {error:.1f}°).")
                        self.send_cgm(CGM.VALKYRIE_YAW_ALIGNED)
                        return True
                time.sleep(0.05)
        finally:
            # Remise à 0 dans tous les cas : pilote/FC reprend le canal yaw
            self._rc_yaw_pwm = 0

        print("[VALKYRIE] Timeout alignement yaw -- passage en LAND quand même.")
        self.send_cgm(CGM.VALKYRIE_YAW_ALIGN_TIMEOUT)
        return False

    # Utilitaire
    def _rc_override_loop(self):
        """
        Thread activé pendant le Precision Loiter et Precision land.
        """
        print("[VALKYRIE] Thread RC Override DÉMARRÉ.")

        while self._precision_active and not getattr(self, 'fin_mission', False):
            self.master.mav.rc_channels_override_send(
                self.master.target_system, self.master.target_component,
                0, 0, self._rc_throttle_pwm, self._rc_yaw_pwm,
                0, 0, 0, 2000
            )
            time.sleep(0.1)

        # Quand on sort de la boucle et on libère la radio
        print("[VALKYRIE] Libération de la radio (Thread RC Override ARRÊTÉ).")
        self.master.mav.rc_channels_override_send(
            self.master.target_system, self.master.target_component,
            0, 0, 0, 0, 0, 0, 0, 0
        )
