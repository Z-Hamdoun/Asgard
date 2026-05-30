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
from pnp.algo import PnPLandingSystem

if TYPE_CHECKING:
    from Communication.class_ESP32_Link import ESP32_Link

# Seuils failsafe (secondes -- indépendants du FPS caméra)
_LOITER_LOCK_DURATION = 3.0   # s -- centrage requis avant de passer en LAND
_LOITER_LOST_TIMEOUT  = 5.0   # s -- cible perdue en LOITER --> requadrillage
_LAND_LOST_TIMEOUT    = 5.0   # s -- cible perdue en LAND --> remontée
_YAW_TOLERANCE_DEG    = 5.0   # ° -- tolérance d'alignement yaw
_ARUCO_CGM_INTERVAL   = 5.0   # s -- intervalle minimum entre deux CGMs ArUco du même type

# Seuils FOLLOW mode
_FOLLOW_ALTITUDE_OFFSET  = 2.0   # m au-dessus de Valhalla (FOLL_OFS_Z = -2.0 en NED)
_FOLLOW_GPS_INIT_TIMEOUT = 10.0  # s max pour recevoir le premier GPS Valhalla
_FOLLOW_GPS_STALENESS    = 5.0   # s sans update GPS Valhalla avant failsafe RTL


class Valkyrie(Drone):
    def __init__(self, address, source_system=255, source_component=mavutil.mavlink.MAV_COMP_ID_MISSIONPLANNER, target_system=None, baud=57600, timeout_heartbeat=None, send_automatic_timesync=True, timesync_delay=3, send_automatic_home_request=True, home_request_delay=3, sysid_to_request_home=None, pos_rate=4, dialect="ardupilotmega", logger = Logger(), camera_topic="/world/iris_runway/model/drone1/model/gimbal/link/pitch_link/sensor/camera/image", camera_wide: bool = False):
        super().__init__(address, source_system, mavutil.mavlink.MAV_COMP_ID_ONBOARD_COMPUTER, target_system, baud, timeout_heartbeat, send_automatic_timesync, timesync_delay, send_automatic_home_request, home_request_delay, sysid_to_request_home, pos_rate, dialect, logger, camera_topic)

        self.camera = Camera(simulation=None,
                             camera_topic="/world/iris_runway/model/drone1/model/gimbal/link/pitch_link/sensor/camera/image",
                             logger=self.logger,
                             wide=camera_wide)

        # Parametres de la mission (écrasés par load_config)
        self.alt_quadrillage  = 5.0
        self.pas_quadrillage  = 2.0
        self.taille_zone      = 10.0
        self.camera_wide      = camera_wide
        self.square_pnp_size  = 33.0   # cm — côté du carré formé par les 4 marqueurs PnP

        # Lien ESP32 pour relayer les CGMs vers Valhalla (pas de liaison radio directe)
        self._esp32_link: ESP32_Link | None = None

        # Offsets mécaniques (m, repère body FRD)
        self.cam_x_m  = 0.0   # camera : offset X par rapport au centre du drone
        self.cam_y_m  = 0.0   # camera : offset Y par rapport au centre du drone
        self.grip_x_m = 0.06   # pince  : offset X sur l'axe du nez (avant positif)

        # Gestion du thread RC
        self._precision_active = False
        self._rc_throttle_pwm = 0
        self._rc_yaw_pwm      = 0   # 0 = pas d'override (pilote/FC reprend le canal)
        self._rc_thread = None

        # Rate-limiting CGMs ArUco (évite le spam)
        self._last_outer_cgm = 0.0
        self._last_inner_cgm = 0.0

        # Lock MAVLink partagé entre les threads (ex: follow_valhalla et heartbeat)
        self._mavlink_lock = threading.Lock()

    def set_esp32_link(self, esp32: ESP32_Link):
        """Enregistre le lien ESP32 utilisé pour router les CGMs via Valhalla."""
        self._esp32_link = esp32

    # =========================================================================
    # LECTURE DE LA CONFIGURATION (VENANT DE VALHALLA VIA ESP32)
    # =========================================================================
    def load_config(self, config_dict: dict) -> bool:
        """
        Extrait les paramètres de la mission depuis le dictionnaire JSON.
        Clés attendues : alt_quadrillage, taille_quadrillage, pas_quadrillage, camera_wide.
        """
        if not config_dict:
            print("[VALKYRIE] Erreur : Dictionnaire de configuration vide.")
            return False

        self.alt_quadrillage = float(config_dict.get("alt_quadrillage", 5.0))
        self.pas_quadrillage = float(config_dict.get("pas_quadrillage", 2.0))
        self.taille_zone     = float(config_dict.get("taille_quadrillage", 10.0))
        self.camera_wide     = bool(config_dict.get("camera_wide", False))
        self.square_pnp_size = float(config_dict.get("square_pnp_size", 33.0))

        # Offset pince pour precision landing
        land_ofs_cm = int(self.grip_x_m * 100)
        self.write_parameter("PLND_LAND_OFS_X", land_ofs_cm,
                             mavutil.mavlink.MAV_PARAM_TYPE_INT8)

        print(f"[VALKYRIE] Config : alt={self.alt_quadrillage}m  "
              f"taille={self.taille_zone}m  pas={self.pas_quadrillage}m  "
              f"camera_wide={self.camera_wide}")
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
        _last_scan_log = 0.0  # log de scan toutes les 5s

        for d_north, d_east in offsets:
            target_lat, target_lon = conv_cart_to_geo((lat_depart, lon_depart), (d_north, d_east))

            print(f"[VALKYRIE] -> Navigation Point {point_actuel}/{total_points}")
            self.logger.log(
                f"[QUADRILLAGE] Point {point_actuel}/{total_points} — "
                f"lat={target_lat:.6f} lon={target_lon:.6f}",
                wanna_print=False,
            )
            self.goto(target_lat, target_lon, self.alt_quadrillage)

            while True:
                if self.fin_mission: return False

                # Scan visuel
                scan = self.camera.analyse_e_aruco if e_analyse else self.camera.analyse
                dx, dy, dz, info, frame = scan(affichage=False)

                # Log périodique "rien détecté" toutes les 5s
                now_t = time.time()
                if info is None and now_t - _last_scan_log >= 5.0:
                    self.logger.log(
                        f"[QUADRILLAGE] Scan point {point_actuel}/{total_points} — rien détecté",
                        wanna_print=False,
                    )
                    _last_scan_log = now_t

                # Cible trouvee
                if info is not None:
                    print("\n==================================================")
                    print(f"[VALKYRIE] CIBLE ARUCO DÉTECTÉE (ID: {info}) !")
                    print(f"[VALKYRIE] Déplacement nécessaire : dx={dx:.3f}m  dy={dy:.3f}m  dz={dz:.3f}m")
                    print("==================================================")
                    self.logger.log(
                        f"[QUADRILLAGE] Cible détectée : {info} | "
                        f"dx={dx:.3f}m  dy={dy:.3f}m  dz={dz:.3f}m",
                        wanna_print=False,
                    )

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
                        self.logger.log(
                            f"[LOITER] Cible acquise — dx={dx:.3f}m  dy={dy:.3f}m  dz={dz:.3f}m",
                            wanna_print=True,
                        )
                    target_lost_since = None

                    elapsed = now - target_locked_since
                    print(f"[LOITER] centrage {elapsed:.1f}/{_LOITER_LOCK_DURATION:.0f}s  "
                          f"dx={dx:.3f}m  dy={dy:.3f}m", end="\r")
                    self.logger.log(
                        f"[LOITER] {elapsed:.1f}s — dx={dx:.3f}m  dy={dy:.3f}m  dz={dz:.3f}m",
                        wanna_print=False,
                    )

                    if elapsed >= _LOITER_LOCK_DURATION:
                        print()
                        print("[VALKYRIE] Centré ! Début de descente (LAND)...")
                        self.logger.log(
                            f"[LOITER] Centré après {elapsed:.1f}s — passage LAND. "
                            f"dx={dx:.3f}m  dy={dy:.3f}m  dz={dz:.3f}m",
                            wanna_print=False,
                        )
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
                        self.logger.log(
                            f"[LOITER] Cible perdue ({_LOITER_LOST_TIMEOUT:.0f}s) — requadrillage.",
                            wanna_print=False,
                        )
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
                    self.logger.log(
                        f"[LAND] dx={dx:.3f}m  dy={dy:.3f}m  dz={dz:.3f}m",
                        wanna_print=False,
                    )
                    land_lost_since = None
                else:
                    if land_lost_since is None:
                        land_lost_since = now
                    if now - land_lost_since >= _LAND_LOST_TIMEOUT:
                        print(f"[VALKYRIE] Cible perdue en LAND ({_LAND_LOST_TIMEOUT:.0f}s) --> remontée.")
                        self.logger.log(
                            f"[LAND] Cible perdue ({_LAND_LOST_TIMEOUT:.0f}s) — remontée.",
                            wanna_print=False,
                        )
                        self.send_cgm(CGM.VALKYRIE_LAND_ABORTED)
                        land_aborted = True
                        break

                if self.motors_disarmed():
                    print("[VALKYRIE] Pose sur l'aruco avec succès !")
                    self.logger.log("[LAND] Moteurs désarmés — pose réussie sur l'ArUco.", wanna_print=False)
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
                        self._align_yaw_to_target()
                        print("[VALKYRIE] Début de descente (LAND)...")
                        self.send_cgm(CGM.VALKYRIE_PRECISION_LAND_STARTING)
                        self._rc_throttle_pwm = 0
                        self.change_mode("LAND")
                        break
                else:
                    if target_lost_since is None:
                        target_lost_since = now
                    # Grâce de 2 s : une perte brève ne remet pas le timer à zéro
                    if now - target_lost_since >= 2.0:
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
    def _align_yaw_to_target(self,
                              tolerance_deg: float = _YAW_TOLERANCE_DEG,
                              timeout: float = 10.0) -> bool:
        """
        Aligne le nez du drone (et la pince) sur l'orientation physique du marqueur
        ArUco en utilisant le vecteur de rotation (rvec) issu d'estimatePoseSingleMarkers.

        Contrairement à atan2(dy, dx), le rvec est stable même quand le drone est
        parfaitement centré (dx≈0, dy≈0) car il décrit la rotation propre du marqueur,
        pas la direction drone→cible.

        La matrice R = Rodrigues(rvec) donne l'axe X du marqueur en repère caméra.
        Transformation caméra→drone (cf. _camera_to_drone réel) :
            drone_forward = -cam_y   →  -R[1,0]
            drone_right   =  cam_x   →   R[0,0]
        angle = atan2(drone_right, drone_forward) = atan2(R[0,0], -R[1,0])
        """
        import cv2 as _cv2

        rvec = getattr(self.camera, '_last_rvec', None)
        if rvec is None:
            print("[VALKYRIE] _align_yaw : rvec absent, alignement ignoré.")
            return False

        R, _ = _cv2.Rodrigues(rvec)
        forward = -R[1, 0]
        right   =  R[0, 0]
        angle_deg = math.degrees(math.atan2(right, forward))

        if abs(angle_deg) < tolerance_deg:
            return True

        _, _, current_yaw_rad = self.angles()
        if math.isnan(current_yaw_rad):
            return False

        target_yaw_deg = (math.degrees(current_yaw_rad) + angle_deg) % 360
        print(f"[VALKYRIE] Alignement yaw (rvec) : {angle_deg:+.1f}° → cible {target_yaw_deg:.1f}°")

        # Correcteur P : ralentit au fur et à mesure qu'on approche la cible
        # → évite l'oscillation bang-bang due à l'inertie en LOITER
        Kp = 2.0  # à ajuster si trop lent (monter à 3.0) ou trop brusque (descendre à 1.5)

        deadline = time.time() + timeout
        try:
            while time.time() < deadline:
                if getattr(self, 'fin_mission', False):
                    return False
                _, _, yaw_rad = self.angles()
                if not math.isnan(yaw_rad):
                    yaw_deg = math.degrees(yaw_rad) % 360
                    # Erreur signée : + = tourner à droite (CW), - = gauche (CCW)
                    error = (target_yaw_deg - yaw_deg + 180) % 360 - 180
                    if abs(error) < tolerance_deg:
                        print(f"[VALKYRIE] Yaw aligné (erreur résiduelle {abs(error):.1f}°).")
                        self.send_cgm(CGM.VALKYRIE_YAW_ALIGNED)
                        return True
                    # PWM proportionnel à l'erreur, borné à [1400, 1600]
                    self._rc_yaw_pwm = max(1400, min(1600, 1500 + int(Kp * error)))
                time.sleep(0.05)
        finally:
            self._rc_yaw_pwm = 0

        print("[VALKYRIE] Timeout alignement yaw -- passage en LAND quand même.")
        self.send_cgm(CGM.VALKYRIE_YAW_ALIGN_TIMEOUT)
        return False

    # =========================================================================
    # FOLLOW MODE (Mission 5)
    # =========================================================================
    def follow_valhalla(self) -> bool:
        """
        Mission 5 : suit Valhalla à _FOLLOW_ALTITUDE_OFFSET mètres au-dessus.

        ArduPilot FOLLOW mode suit un drone en lisant ses messages GLOBAL_POSITION_INT
        sur le bus MAVLink. On injecte ces messages avec srcSystem=1 (sysid Valhalla)
        en utilisant le GPS reçu via ESP32

        Prérequis FC : FOLL_ENABLE=1 doit être préconfiguré (nécessite un reboot).

        Returns:
            True  : mission terminée normalement (fin_mission reçu)
            False : erreur (ESP32 absent, décollage échoué, GPS Valhalla perdu)
        """
        if self._esp32_link is None:
            print("[FOLLOW] Lien ESP32 non configuré. Abandon.")
            return False

        # Paramètres FOLLOW -- FOLL_ENABLE doit être à 1 avant reboot
        # FOLL_SYSID=1 : on va injecter des GLOBAL_POSITION_INT avec srcSystem=1
        # FOLL_ALT_TYPE=0 : utilise relative_alt (altitude au-dessus de la home)
        #   valhalla_alt reçu via ESP32 = résultat de drone.position()[2] = relative_alt
        self.write_parameter("FOLL_SYSID",     1,                               mavutil.mavlink.MAV_PARAM_TYPE_INT32)
        self.write_parameter("FOLL_ALT_TYPE",  0,                               mavutil.mavlink.MAV_PARAM_TYPE_INT8)
        self.write_parameter("FOLL_OFS_Z",     float(-_FOLLOW_ALTITUDE_OFFSET), mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
        self.write_parameter("FOLL_OFS_TYPE",  0,                               mavutil.mavlink.MAV_PARAM_TYPE_INT8)
        self.write_parameter("FOLL_YAW_BEHAV", 0,                               mavutil.mavlink.MAV_PARAM_TYPE_INT8)
        time.sleep(0.5)

        if not self.takeoff_autonome(self.alt_quadrillage):
            return False

        # Attente du premier GPS Valhalla reçu via ESP32
        print("[FOLLOW] En attente du GPS Valhalla (ESP32)...")
        deadline = time.time() + _FOLLOW_GPS_INIT_TIMEOUT
        while time.time() < deadline:
            if self.fin_mission:
                return True
            if self._esp32_link.valhalla_gps_timestamp is not None:
                break
            time.sleep(0.1)
        else:
            print("[FOLLOW] GPS Valhalla non disponible. RTL.")
            self.send_cgm(CGM.VALKYRIE_NO_TARGET_FOUND)
            self.return_to_launch()
            return False

        # Passage en mode FOLLOW
        follow_engaged = False
        for _ in range(5):
            if self.change_mode("FOLLOW"):
                follow_engaged = True
                break
            time.sleep(1.0)

        if not follow_engaged:
            print("[FOLLOW] Impossible de passer en mode FOLLOW. RTL.")
            self.send_cgm(CGM.VALKYRIE_MODE_CHANGE_FAIL)
            self.return_to_launch()
            return False

        print("[FOLLOW] Mode FOLLOW activé. Injection GPS Valhalla (srcSystem=1) démarrée.")
        self.send_cgm(CGM.VALKYRIE_FOLLOW_STARTED)

        # Boucle principale : injection GLOBAL_POSITION_INT à 10 Hz
        # On usurpe temporairement srcSystem=1 (sysid Valhalla) avec un Lock pour
        # éviter qu'un autre thread envoie un message avec la mauvaise identité.
        while True:
            if self.fin_mission:
                return True

            ts = self._esp32_link.valhalla_gps_timestamp
            if ts is None or (time.time() - ts) > _FOLLOW_GPS_STALENESS:
                print(f"[FOLLOW] GPS Valhalla perdu (>{_FOLLOW_GPS_STALENESS:.0f}s). RTL.")
                self.send_cgm(CGM.VALKYRIE_FOLLOW_GPS_LOST)
                self.return_to_launch()
                return False

            lat     = self._esp32_link.valhalla_lat
            lon     = self._esp32_link.valhalla_lon
            rel_alt = self._esp32_link.valhalla_alt      # m above home -- position()[2]
            alt_msl = self._esp32_link.valhalla_alt_msl  # m MSL        -- position()[3]

            if lat is not None and lon is not None and rel_alt is not None and alt_msl is not None:
                with self._mavlink_lock:
                    orig_sysid = self.master.mav.srcSystem
                    orig_comp  = self.master.mav.srcComponent
                    try:
                        self.master.mav.srcSystem    = 1  # usurpe l'identité de Valhalla
                        self.master.mav.srcComponent = 1
                        self.master.mav.global_position_int_send(
                            self.time_boot_ms,      # time_boot_ms
                            int(lat * 1e7),         # lat          (degE7)
                            int(lon * 1e7),         # lon          (degE7)
                            int(alt_msl  * 1000),   # alt          (mm MSL) <-- EKF sanity check
                            int(rel_alt  * 1000),   # relative_alt (mm above home) <-- FOLL_ALT_TYPE=0
                            0,                      # vx  (cm/s)
                            0,                      # vy  (cm/s)
                            0,                      # vz  (cm/s)
                            0xFFFF                  # hdg 
                        )
                    finally:
                        self.master.mav.srcSystem    = orig_sysid 
                        self.master.mav.srcComponent = orig_comp

            time.sleep(0.1)  # 10 Hz

    # =========================================================================
    # APPROCHE VALHALLA EN FOLLOW MODE (Mission 1 -- phase livraison)
    # =========================================================================
    def approach_valhalla_follow(self, timeout: float = 120.0) -> bool:
        """
        Configure et active le mode FOLLOW pour s'approcher de Valhalla à
        _FOLLOW_ALTITUDE_OFFSET mètres au-dessus. Retourne dès que Valkyrie
        est à moins de 2.5m (GPS horizontal) de Valhalla.

        Prérequis : FOLL_ENABLE=1 préconfiguré sur le FC (nécessite reboot).
        Prérequis : GPS Valhalla disponible via ESP32 (valhalla_lat/lon/alt).

        Returns:
            True  : Valkyrie positionné au-dessus de Valhalla
            False : timeout ou GPS Valhalla non disponible
        """
        if self._esp32_link is None:
            print("[FOLLOW] Lien ESP32 non configuré. Abandon.")
            return False

        self.write_parameter("FOLL_SYSID",     1,                               mavutil.mavlink.MAV_PARAM_TYPE_INT32)
        self.write_parameter("FOLL_ALT_TYPE",  0,                               mavutil.mavlink.MAV_PARAM_TYPE_INT8)
        self.write_parameter("FOLL_OFS_Z",     float(-_FOLLOW_ALTITUDE_OFFSET), mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
        self.write_parameter("FOLL_OFS_TYPE",  0,                               mavutil.mavlink.MAV_PARAM_TYPE_INT8)
        self.write_parameter("FOLL_YAW_BEHAV", 0,                               mavutil.mavlink.MAV_PARAM_TYPE_INT8)
        time.sleep(0.5)

        # Attente du premier GPS Valhalla
        print("[FOLLOW] Attente GPS Valhalla...")
        deadline_gps = time.time() + _FOLLOW_GPS_INIT_TIMEOUT
        while time.time() < deadline_gps:
            if self.fin_mission:
                return False
            if self._esp32_link.valhalla_gps_timestamp is not None:
                break
            time.sleep(0.1)
        else:
            print("[FOLLOW] GPS Valhalla non disponible. Abandon.")
            return False

        # Passage en FOLLOW
        for _ in range(5):
            if self.change_mode("FOLLOW"):
                break
            time.sleep(1.0)
        else:
            print("[FOLLOW] Impossible de passer en mode FOLLOW.")
            self.send_cgm(CGM.VALKYRIE_MODE_CHANGE_FAIL)
            return False

        print("[FOLLOW] Mode FOLLOW activé. Injection GPS Valhalla en cours...")
        self.send_cgm(CGM.VALKYRIE_FOLLOW_STARTED)

        _PROXIMITY_M = 2.5  # distance GPS horizontale pour considérer "arrivé"
        deadline = time.time() + timeout

        while time.time() < deadline:
            if self.fin_mission:
                return False

            ts = self._esp32_link.valhalla_gps_timestamp
            if ts is None or (time.time() - ts) > _FOLLOW_GPS_STALENESS:
                print("[FOLLOW] GPS Valhalla perdu. RTL.")
                self.send_cgm(CGM.VALKYRIE_FOLLOW_GPS_LOST)
                self.return_to_launch()
                return False

            lat_v = self._esp32_link.valhalla_lat
            lon_v = self._esp32_link.valhalla_lon
            rel_v = self._esp32_link.valhalla_alt
            msl_v = self._esp32_link.valhalla_alt_msl

            if lat_v is not None and lon_v is not None and rel_v is not None and msl_v is not None:
                # Injection du GPS Valhalla avec srcSystem=1
                with self._mavlink_lock:
                    orig_sys  = self.master.mav.srcSystem
                    orig_comp = self.master.mav.srcComponent
                    try:
                        self.master.mav.srcSystem    = 1
                        self.master.mav.srcComponent = 1
                        self.master.mav.global_position_int_send(
                            self.time_boot_ms,
                            int(lat_v * 1e7),
                            int(lon_v * 1e7),
                            int(msl_v * 1000),
                            int(rel_v * 1000),
                            0, 0, 0, 0xFFFF,
                        )
                    finally:
                        self.master.mav.srcSystem    = orig_sys
                        self.master.mav.srcComponent = orig_comp

                # Vérification de proximité (distance GPS horizontale)
                dist = self.get_distance_with(lat_v, lon_v)
                if not math.isnan(dist) and dist < _PROXIMITY_M:
                    print(f"[FOLLOW] Valkyrie au-dessus de Valhalla (dist={dist:.1f}m). Passage LOITER.")
                    self.change_mode("LOITER")
                    return True

            time.sleep(0.1)

        print("[FOLLOW] Timeout approche Valhalla.")
        return False

    # =========================================================================
    # CENTRAGE PnP AU-DESSUS DE VALHALLA (Mission 1 -- phase livraison)
    # =========================================================================
    def pnp_center_over_valhalla(self, timeout: float = 60.0) -> bool:
        """
        En mode LOITER, utilise PnPLandingSystem pour détecter les 4 marqueurs
        circulaires de Valhalla et corriger la position via LANDING_TARGET jusqu'à
        être bien centré.

        Returns:
            True  : centré (|dx| < 0.15m et |dy| < 0.15m pendant 3s consécutives)
            False : timeout ou fin_mission
        """
        _CENTER_THRESHOLD_M  = 0.15  # m
        _CENTER_LOCK_DURATION = 3.0  # s consécutives sous le seuil

        pnp = PnPLandingSystem(
            marker_distance=self.square_pnp_size / 100.0,
            camera_matrix=self.camera._camera_matrix,
            dist_coeffs=self.camera._dist_coeffs,
        )
        centered_since = None
        deadline = time.time() + timeout

        print("[PnP] Centrage sur Valhalla en cours...")

        while time.time() < deadline:
            if self.fin_mission:
                return False

            frame = self.camera.get_frame(timeout=2)
            if frame is None:
                time.sleep(0.05)
                continue

            result = pnp.get_landing_vector(frame)

            # Erreurs internes du PnP (< 4 points, échec solvePnP...)
            if not isinstance(result, tuple) or len(result) != 3:
                time.sleep(0.05)
                continue
            dx, dy, dz = result
            if not (isinstance(dx, float) and isinstance(dy, float)):
                time.sleep(0.05)
                continue

            self.send_landing_target(dx, dy, dz)
            print(f"[PnP] dx={dx:.3f}m dy={dy:.3f}m dz={dz:.3f}m", end="\r")

            now = time.time()
            if abs(dx) < _CENTER_THRESHOLD_M and abs(dy) < _CENTER_THRESHOLD_M:
                if centered_since is None:
                    centered_since = now
                elif now - centered_since >= _CENTER_LOCK_DURATION:
                    print(f"\n[PnP] Centré sur Valhalla ({_CENTER_LOCK_DURATION:.0f}s stable).")
                    return True
            else:
                centered_since = None

            time.sleep(0.05)

        print("\n[PnP] Timeout centrage PnP.")
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
