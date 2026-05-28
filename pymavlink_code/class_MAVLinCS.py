import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from pymavlink import mavutil
import time
from geopy.distance import distance
from geopy.point import Point
from math import atan2, asin, sqrt, degrees, radians, cos, log, tan, pi, isnan
import unicodedata

import pymavlink_code.code_de_gestion_de_missions as CGM
from pymavlink_code.class_Statustext_Receiver import Statustext_Receiver
from pymavlink_code.class_Timesync_Handler import Timesync_Handler
from pymavlink_code.class_MavThread import MavThread
from utils.class_Logger import Logger

# Disclaimer : cette classe a de base été créée pour être utilisée sur ArduPilot.
# Cependant, PX4 a été implémenté à de nombreux endroits mais non testé.

class MAVLinCS:
    """Permet de se connecter à un ou plusieurs contrôleur(s) de vol"""
    def __init__(self,
            address: str,
            source_system: int = 255,
            source_component: int = mavutil.mavlink.MAV_COMP_ID_MISSIONPLANNER,
            target_system: int | None = None,
            baud: int = 57600,
            timeout_heartbeat: float | None = None,
            send_automatic_timesync: bool = True,
            timesync_delay: int = 3,
            send_automatic_home_request: bool = True,
            home_request_delay: int = 3,
            sysid_to_request_home: None | int | list[int] = None,
            pos_rate: float = 4,
            dialect: str = "ardupilotmega",
            logger: Logger = Logger()
        ):
        """Initialise la connexion.

        Args:
            address (str): Adresse de connexion.
            source_system (int): ID MAVLink de la station au sol.
            source_component (int): MAV_COMPONENT de la station au sol.
            target_system (int | None): ID MAVLink du contrôleur de vol target (s'il y en a un). None si on prend l'ID du premier véhicule détecté.
            baud (int): Baudrate de connexion.
            timeout_heartbeat (float): Timeout (s) d'attente de HEARTBEAT avant de considérer la connexion impossible. None si pas de timeout. 0 si on ne veut pas attendre le 1er HEARTBEAT (nécessite le bon dialect MAVLink, présuppose l'utilisation de MAVLink 2).
            send_automatic_timesync (bool): Indique si on veut envoyer des TIMESYNC à intervalle régulier ou non.
            timesync_delay (int): Temps d'attente (s) entre l'envoi de 2 TIMESYNC automatiques.
            send_automatic_home_request (bool): Indique si on veut demander la position HOME à intervalle régulier ou non.
            home_request_delay (int): Temps d'attente (s) entre l'envoi de 2 demandes de position HOME automatiques.
            sysid_to_request_home (None | int | list[int]): Liste des sysid à qui demander la position HOME régulièrement. None = seulement le master.
            pos_rate (float): Fréquence d'envoi de la position GPS par le contrôleur de vol vers notre station au sol.
            dialect (str): dialect MAVLink, essentiel si timeout_heartbeat == 0. 'ardupilotmega' pour ArduPilot, 'common' pour PX4.
            logger (Logger): Objet permettant de log.
        """
        # -----------------------------------
        # Variables données par l'utilisateur
        # -----------------------------------

        self._data_init: dict = {
            "address": address,
            "target_system": target_system,
            "source_system": source_system,
            "source_component": source_component,
            "baud": baud,
            "pos_rate": pos_rate,
            "dialect": dialect
        }
        """Dictionnaire avec des données d'initialisation, permettant de ne pas créer trop de variables inutiles."""

        self._sysid_to_request_home: None | int | list[int] = sysid_to_request_home
        """Liste des sysid à qui demander la position HOME régulièrement. None = seulement le master."""

        self._send_automatic_home_request: bool = send_automatic_home_request
        """Indique si on veut demander la position HOME à intervalle régulier ou non."""

        self._home_request_delay: int = home_request_delay
        """Temps d'attente (s) entre l'envoi de 2 demandes de position HOME automatiques."""

        self.logger: Logger = logger
        """Objet permettant de log."""

        # -------------------
        # Variables générales
        # -------------------

        self._time_boot: float = time.time()
        """time.time() lors de la création de l'objet."""

        self._nb_heartbeat_since_last_home_request: int = home_request_delay
        """Variable permettant de compter les HEARTBEAT envoyés pour la demande"""

        self.mavthread: MavThread = MavThread(master=None)
        """Objet de gestion des threads."""

        self.statustext_receiver: Statustext_Receiver = Statustext_Receiver()
        """Objet de gestion des STATUSTEXT."""

        self.timesync_handler: Timesync_Handler = Timesync_Handler(
            master=None,
            send_automatic_timesync=send_automatic_timesync,
            timesync_delay=timesync_delay,
            logger=logger
        )
        """Objet de gestion des TIMESYNC."""

        self.cgm: set = set()
        """set contenant les CGM reçus et envoyés."""

        self._cgm_hook = None
        """Callback optionnel appelé à chaque CGM reçu : cb(cgm_object)."""

        self.master: mavutil.mavfile | None = None 
        """Objet master permettant de communiquer en MAVLink."""

        self.fin_mission: bool = False
        """Indique si on doit stopper le code ou pas (permet de ne plus faire d'actions et d'arrêter les fonctions bloquantes)."""

        self.allow_actions: bool = True
        """Indique si on autorise l'envoi de commandes de vol (armement, désarmement, changement de mode, etc.)."""

        # Ouverture de la connexion
        self.open(timeout_heartbeat=timeout_heartbeat)

    # --------------------------------------------------------
    # Temps depuis le début de la création de l'objet MAVLinCS
    # --------------------------------------------------------

    @property
    def time_boot(self) -> int:
        """Temps depuis le démarrage en s"""
        return int(time.time() - self._time_boot)

    @property
    def time_boot_ms(self) -> int:
        """Temps depuis le démarrage en ms"""
        return int((time.time() - self._time_boot) * 1e3)

    @property
    def time_usec(self) -> int:
        """timestamp Unix en us"""
        return int(time.time() * 1e6)

    # -------
    # Données
    # -------

    def position(self, source_system: int | None = None) -> tuple[float, float, float, float]:
        """Position GPS.

        Args:
            source_system (int | None): ID MAVLink source de l'appareil. Par défaut, vaut celui du master.

        Returns:
            tuple:
                - **latitude** (*float*) – latitude en degrés. NaN si aucune donnée reçue.
                - **longitude** (*float*) – longitude en degrés. NaN si aucune donnée reçue.
                - **relative_altitude** (*float*) – altitude relative en mètres. NaN si aucune donnée reçue.
                - **altitude** (*float*) – altitude absolue (MSL) en mètres. NaN si aucune donnée reçue.
        """
        m = self.get_msg(
            msg_type="GLOBAL_POSITION_INT",
            source_system=source_system
        )
        if m:
            return m.lat / 1e7, m.lon / 1e7, m.relative_alt / 1e3, m.alt / 1e3
        return float('NaN'), float('NaN'), float('NaN'), float('NaN')

    def angles(self, source_system: int | None = None) -> tuple[float, float, float]:
        """Angles.

        Args:
            source_system (int | None): ID MAVLink source de l'appareil. Par défaut, vaut celui du master.

        Returns:
            tuple:
                - **roll** (*float*) – Rotation autour de l'axe longitudinal (avant-arrière) ([-pi ; +pi] rad). NaN si aucune donnée reçue.
                - **pitch** (*float*) – Rotation autour de l'axe latéral (gauche-droite) ([-pi ; +pi] rad). NaN si aucune donnée reçue.
                - **yaw** (*float*) – Rotation autour de l'axe vertical (haut-bas) ([-pi ; +pi] rad). NaN si aucune donnée reçue.
        """
        m = self.get_msg(
            msg_type="ATTITUDE",
            source_system=source_system
        )
        if m:
            return m.roll, m.pitch, m.yaw
        return float('NaN'), float('NaN'), float('NaN')

    def angles_speed(self, source_system: int | None = None) -> tuple[float, float, float]:
        """Vitesses angulaires.

        Args:
            source_system (int | None): ID MAVLink source de l'appareil. Par défaut, vaut celui du master.

        Returns:
            tuple:
                - **rollspeed** (*float*) – Vitesse de rotation autour de l'axe longitudinal (avant-arrière) (rad/s). NaN si aucune donnée reçue.
                - **pitchspeed** (*float*) – Vitesse de rotation autour de l'axe latéral (gauche-droite) (rad). NaN si aucune donnée reçue.
                - **yawspeed** (*float*) – Vitesse de rotation autour de l'axe vertical (haut-bas) (rad). NaN si aucune donnée reçue.
        """
        m = self.get_msg(
            msg_type="ATTITUDE",
            source_system=source_system
        )
        if m:
            return m.rollspeed, m.pitchspeed, m.yawspeed
        return float('NaN'), float('NaN'), float('NaN')

    def speed(self, source_system: int | None = None) -> tuple[float, float, float]:
        """Vitesses.

        Args:
            source_system (int | None): ID MAVLink source de l'appareil. Par défaut, vaut celui du master.

        Returns:
            tuple:
                - **vx** (*float*) – Vitesse en m/s vers le Nord. NaN si aucune donnée reçue.
                - **vy** (*float*) – Vitesse en m/s vers l'Est. NaN si aucune donnée reçue.
                - **vz** (*float*) – Vitesse en m/s vers le bas. NaN si aucune donnée reçue.
        """
        m = self.get_msg(
            msg_type="GLOBAL_POSITION_INT",
            source_system=source_system
        )
        if m:
            return m.vx / 1e2, m.vy / 1e2, m.vz / 1e2
        return float('NaN'), float('NaN'), float('NaN')

    def speed_module(self, source_system: int | None = None) -> float:
        """Vitesse absolue.

        Args:
            source_system (int | None): ID MAVLink source de l'appareil. Par défaut, vaut celui du master.

        Returns:
            float: Vitesse en m/s. NaN si aucune donnée reçue.
        """
        vx, vy, vz = self.speed(source_system=source_system)
        if isnan(vx) and isnan(vy) and isnan(vz):
            return float('NaN')
        return sqrt(vx**2+vy**2+vz**2)

    def motors_armed(self, source_system: int | None = None) -> bool | None:
        """Statut d'armement.

        Args:
            source_system (int | None): ID MAVLink source à vérifier. Par défaut, vaut celui du master.

        Returns:
            bool | None: True si le drone est armé, False sinon. None si pas de donnée reçue.
        """
        hb = self.get_msg(
            msg_type="HEARTBEAT",
            source_system=source_system
        )
        if hb is None:
            return None
        return bool(hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)

    def motors_disarmed(self, source_system: int | None = None) -> bool | None:
        """Statut de désarmement.

        Args:
            source_system (int | None): ID MAVLink source à vérifier. Par défaut, vaut celui du master.

        Returns:
            bool | None: True si le drone est désarmé, False sinon. None si pas de donnée reçue.
        """
        hb = self.get_msg(
            msg_type="HEARTBEAT",
            source_system=source_system
        )
        if hb is None:
            return None
        return not bool(hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)

    def mode(self, source_system: int | None = None) -> str:
        """Mode de vol.

        Args:
            source_system (int | None): ID MAVLink de l'appareil. Par défaut, vaut celui du master.

        Returns:
            str: Mode du contrôleur de vol. "UNKNOW" si aucune donnée valable reçue.
        """
        if float(mavutil.mavlink.WIRE_PROTOCOL_VERSION) >= 1:
            # MAVLink 1 ou MAVLink 2
            hb = self.get_msg(
                msg_type="HEARTBEAT",
                source_system=source_system
            )
            if hb:
                return mavutil.mode_string_v10(hb)
            # Fallback: On regarde les messages HIGH_LATENCY2
            high_latency2 = self.get_msg(
                msg_type="HIGH_LATENCY2",
                source_system=source_system
            )
            if high_latency2:
                return mavutil.mode_string_v10(high_latency2)
            return "UNKNOW"
        elif float(mavutil.mavlink.WIRE_PROTOCOL_VERSION) == '0.9':
            # MAVLink 0.9
            sys_status = self.get_msg(
                msg_type="SYS_STATUS",
                source_system=source_system
            )
            if sys_status:
                return mavutil.mode_string_v09(sys_status)
            return "UNKNOW"
        return "UNKNOW"

    def custom_mode(self, source_system: int | None = None) -> int:
        """Mode de vol en int (ArduPilot). Sur PX4, permet de trouver le Custom Main Mode et Custom Sub Mode.

        Args:
            source_system (int | None): ID MAVLink de l'appareil. Par défaut, vaut celui du master.

        Returns:
            int: Mode du contrôleur de vol. NaN si aucune donnée reçue.
        """
        hb = self.get_msg(
            msg_type="HEARTBEAT",
            source_system=source_system
        )
        if hb:
            return hb.custom_mode
        # Fallback: On regarde les HIGH_LATENCY2
        high_latency2 = self.get_msg(
            msg_type="HIGH_LATENCY2",
            source_system=source_system
        )
        if high_latency2:
            return high_latency2.custom_mode
        return float('NaN')

    def base_mode(self, source_system: int | None = None) -> int:
        """Base Mode. Permet en partie de caractériser le mode sur PX4.

        Args:
            source_system (int | None): ID MAVLink de l'appareil. Par défaut, vaut celui du master.

        Returns:
            int: Base Mode. NaN si aucune donnée reçue.
        """
        hb = self.get_msg(
            msg_type="HEARTBEAT",
            source_system=source_system
        )
        if hb:
            return hb.base_mode
        return float('NaN')

    def custom_main_mode(self, source_system: int | None = None) -> int:
        """Custom Main Mode (PX4). Permet en partie de caractériser le mode sur PX4.

        Args:
            source_system (int | None): ID MAVLink de l'appareil. Par défaut, vaut celui du master.

        Returns:
            int: Custom Main Mode du contrôleur de vol. NaN si aucune donnée reçue.
        """
        custom_mode = self.custom_mode(source_system=source_system)
        if isnan(custom_mode):
            return float('NaN')
        return (custom_mode & 0xFF0000) >> 16

    def custom_sub_mode(self, source_system: int | None = None) -> int:
        """Custom Sub Mode (PX4). Permet en partie de caractériser le mode sur PX4.

        Args:
            source_system (int | None): ID MAVLink de l'appareil. Par défaut, vaut celui du master.

        Returns:
            int: Custom Sub Mode du contrôleur de vol. NaN si aucune donnée reçue.
        """
        custom_mode = self.custom_mode(source_system=source_system)
        if isnan(custom_mode):
            return float('NaN')
        return (custom_mode & 0xFF000000) >> 24

    def autopilot_int(self, source_system: int | None = None) -> int:
        """Autopilot.

        Args:
            source_system (int | None): ID MAVLink de l'appareil. Par défaut, vaut celui du master.

        Returns:
            int: MAV_AUTOPILOT | Autopilot. NaN si aucune donnée reçue.
        """
        m = self.get_msg(
            msg_type="HEARTBEAT",
            source_system=source_system
        )
        if m:
            return m.autopilot
        return float('NaN')

    def autopilot_str(self, source_system: int | None = None) -> str:
        """Autopilot.

        Args:
            source_system (int | None): ID MAVLink de l'appareil. Par défaut, vaut celui du master.

        Returns:
            str: Autopilot (ex: PX4, ARDUPILOTMEGA). UNKNOW si aucune donnée reçue.
        """
        m = self.get_msg(
            msg_type="HEARTBEAT",
            source_system=source_system
        )
        if m:
            return mavutil.mavlink.enums["MAV_AUTOPILOT"][m.autopilot].name[14:]
        return "UNKNOW"

    def battery(self, source_system: int | None = None) -> int:
        """Batterie restante (pas très fiable en vrai, nécessite d'avoir bien paramétré le contrôleur de vol).

        Args:
            source_system (int | None): ID MAVLink source. Par défaut, vaut celui du master.

        Returns:
            int: Pourcentage de batterie restant. NaN si aucune donnée reçue.
        """
        m = self.get_msg(
            msg_type="SYS_STATUS",
            source_system=source_system
        )
        if m:
            return m.battery_remaining
        return float('NaN')

    def battery_voltage(self, source_system: int | None = None) -> float:
        """Tension de batterie.

        Args:
            source_system (int | None): ID MAVLink source. Par défaut, vaut celui du master.

        Returns:
            float: Tension de batterie en V. NaN si aucune donnée reçue.
        """
        if source_system is None:
            source_system = self.master.target_system
        m = self.get_msg(
            msg_type="SYS_STATUS",
            source_system=source_system
        )
        if m:
            return m.voltage_battery / 1e3 if m.voltage_battery != 65535 else float('NaN')
        return float('NaN')

    def gps_fix(self, source_system: int | None = None) -> bool | None:
        """Statut du GPS 3D fix.

        Args:
            source_system (int | None): ID MAVLink de l'appareil. Par défaut, vaut celui du master.

        Returns:
            bool | None: GPS 3D fix ou non. None si aucune donnée reçue.
        """
        m = self.get_msg(
            msg_type="GPS_RAW_INT",
            source_system=source_system
        )
        if m is None:
            return None
        return bool(m.fix_type>=3 and m.lat != 0) # Tiré de pymavlink

    def servo_value(self, servo_channel: int, source_system: int | None = None) -> float:
        """PWM du servo.

        Args:
            servo_channel (int): Channel du servo (1-16 ou 1-8 pour d'anciennes versions).
            source_system (int | None): ID MAVLink de l'appareil. Par défaut, vaut celui du master.

        Returns:
            float: Valeur PWM. NaN si aucune donnée reçue.
        """
        m = self.get_msg(
           msg_type="SERVO_OUTPUT_RAW",
           source_system=source_system
        )
        if m is None:
            return float('NaN')
        return getattr(m, f"servo{servo_channel}_raw", float('NaN'))

    def gimbal_angles(self) -> tuple[float, float, float]:
        """Angles du gimbal en deg.

        Returns:
            tuple:
                - **roll** (*float*) – Roll en deg. NaN si aucune donnée reçue.
                - **pitch** (*float*) – Pitch en deg. NaN si aucune donnée reçue.
                - **yaw** (*float*) – Yaw en deg. NaN si aucune donnée reçue.
        """
        m = self.get_msg(msg_type="GIMBAL_DEVICE_ATTITUDE_STATUS")
        if m is None:
            return float('NaN'), float('NaN'), float('NaN')

        w, x, y, z = m.q

        # Formules classiques de conversion quaternion -> Euler (Z-Y-X convention)
        sinp = 2 * (w * y - z * x)
        sinp = max(min(sinp, 1.0), -1.0)

        roll = atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
        pitch = asin(sinp)
        yaw = atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))

        return degrees(roll), degrees(pitch), degrees(yaw)

    def current_waypoint_index(self, source_system: int | None = None) -> int:
        """Waypoint actuel.

        Args:
            source_system (int | None): ID MAVLink source à vérifier. Par défaut, vaut celui du master.

        Returns:
            int: Numéro de séquence du waypoint. NaN si aucune donnée reçue.
        """
        m = self.get_msg(
            msg_type="MISSION_CURRENT",
            source_system=source_system
        )
        if m:
            return m.seq
        return float('NaN')

    def is_waypoint_mission_completed(self, source_system: int | None = None) -> bool | None:
        """Regarde si la mission de waypoints est terminée ou non.

        Args:
            source_system (int | None): ID MAVLink source. Par défaut, vaut celui du master.

        Returns:
            bool | None: True si la mission est finie, False sinon. None si aucune donnée reçue.
        """
        m = self.get_msg(
            msg_type="MISSION_CURRENT",
            source_system=source_system
        )
        if m is None:
            return None
        if hasattr(m, "mission_state"):
            return bool(m.mission_state == mavutil.mavlink.MISSION_STATE_NOT_STARTED)
        return bool(m.seq == 0) # On suppose qu'être au wp 0 <=> Mission non démarrée

    def home_position(self, source_system: int | None = None) -> tuple[float, float, float]:
        """Position HOME.

        Args:
            source_system (int | None): ID MAVLink source de la position HOME. Par défaut, vaut celui du master.

        Returns:
            tuple:
                - **latitude_home** (*float*) – Latitude HOME. NaN si pas de donnée reçue.
                - **longitude_home** (*float*) – Longitude HOME. NaN si pas de donnée reçue.
                - **altitude_home** (*float*) – Altitude HOME (MSL). NaN si pas de donnée reçue.
        """
        m = self.get_msg(
            msg_type="HOME_POSITION",
            source_system=source_system
        )
        if m:
            return m.latitude / 1e7, m.longitude / 1e7, m.altitude / 1e3
        return float('NaN'), float('NaN'), float('NaN')

    def get_distance_with(self,
            lat: float,
            lon: float,
            relative_alt: float | None = None,
            alt: float | None = None
        ) -> float:
        """Distance entre le contrôleur de vol et un point GPS.

        Args:
            lat (float): Latitude du point GPS (en degrés).
            lon (float): Longitude du point GPS (en degrés).
            relative_alt (float): Altitude relative du point GPS (en mètres).
            alt (float): Altitude absolue (MSL) du point GPS (en mètres).

        Returns:
            float: Distance en mètres. NaN si aucune donnée GPS reçue.
        """
        # Fonction copiée de MAVProxy
        lat_gps, lon_gps, relative_alt_gps, alt_gps = self.position()
        if isnan(lat_gps) and isnan(lon_gps) and isnan(relative_alt_gps) and isnan(alt_gps):
            return float('NaN')
        lat1 = radians(lat)
        lon1 = radians(lon)
        lat2 = radians(lat_gps)
        lon2 = radians(lon_gps)
        if abs(lat2-lat1) < 1.0e-15:
            q = cos(lat1)
        else:
            q = (lat2-lat1)/log(tan(lat2/2+pi/4)/tan(lat1/2+pi/4))
        d = sqrt((lat2-lat1)**2 + q**2 * (lon2-lon1)**2)
        dist = d * 6378100.0
        if alt is not None:
            return sqrt(dist**2 + (alt_gps-alt)**2) # On renvoie la distance sur le plan horizontal
        if relative_alt is not None:
            return sqrt(dist**2 + (relative_alt_gps-relative_alt)**2)
        return dist

    def get_latence_ms_with_sysidcompid(self, key: tuple[int, int]) -> int:
        """Renvoie la latence estimée d'un aller entre la station au sol et un appareil.

        Args:
            key (tuple[int, int]): (sysid, compid)

        Returns:
            int: Latence en ms. NaN si aucune donnée reçue.
        """
        return self.timesync_handler.get_latence_ms_with_sysidcompid(key=key)

    # ---------
    # Commandes
    # ---------

    def set_servo(self,
            servo_channel: int,
            pwm: int,
            timeout_ack: float | None = 2,
            target_system: int | None = None
        ) -> bool:
        """Choisi la position d'un servo.

        Args:
            servo_channel (int): Channel du servo.
            pwm (int): valeur PWM (entre 1000 et 2000. 1000=fermé, 2000=ouvert).
            timeout_ack (float | None): Temps d'attente d'ack. 0 si pas d'attente (renvoie False). None si pas de timeout.
            target_system (int | None): ID MAVLink cible de la commande. Par défaut, vaut celui du master.

        Returns:
            bool: Résultat de l'opération.
        """
        if self.fin_mission:
            self.logger.log("[FAIL] Mission stopped: Impossible to set PWM")
            return False
        
        if not self.allow_actions:
            self.logger.log("[FAIL] Actions not allowed: Impossible to set PWM")
            return False

        if target_system is None:
            target_system = self.master.target_system
        
        # A vérifier, mais dans certains cas, si le PWM du servo est déjà celui qu'on souhaite lui donner, il n'envoie pas d'ACK (pas sûr)

        if pwm < 1000 or pwm > 2000:
            self.logger.log(f"[FAIL] PWM: {pwm} must be between 1000 and 2000")
            return False

        self.logger.log(f"[INFO] Sending servo request to {target_system}. Channel: {servo_channel}, PWM: {pwm}")
        self.master.mav.command_long_send(
            target_system, # target_system
            mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1, # target_component
            mavutil.mavlink.MAV_CMD_DO_SET_SERVO, # Commande pour contrôler un servo
            1, # confirmation
            servo_channel, # param1 (Instance)
            pwm, # param2 (PWM)
            0,0,0,0,0 # param3-7 (unused)
        )

        accepted = self.wait_command_ack(
            command=mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
            timeout=timeout_ack,
            source_system=target_system
        )
        if accepted:
            self.logger.log("[SUCCESS] PWM set")
        else:
            self.logger.log("[FAIL] PWM not set")
        return bool(accepted)

    def set_gimbal_target(self,
            latitude: float,
            longitude: float,
            altitude: float,
            timeout_ack: float = 3
        ) -> bool:
        """Envoie une position GPS cible.

        Args:
            latitude (float): Latitude en deg.
            longitude (float): Longitude en deg.
            altitude (float): Altitude absolue (MSL) en m.
            timeout_ack (float): Timeout d'attente d'ACK en s.

        Returns:
            bool: Résultat de l'opération.
        """
        # Fonction pas testée mais devrait fonctionner en changeant le mode de la gimbal (fonction à implémenter)
        self.logger.log("[INFO] Sending Gimbal location request..", wanna_print=False)
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_ROI_LOCATION,
            1,0,0,0,0,
            int(latitude*1e7),
            int(longitude*1e7),
            altitude
        )
        ack_received = self.wait_command_ack(
            command=mavutil.mavlink.MAV_CMD_DO_SET_ROI_LOCATION,
            timeout=timeout_ack
        )
        if ack_received:
            self.logger.log("[SUCCESS] Gimbal target set", wanna_print=False)
        else:
            self.logger.log("[FAIL] Gimbal target not set", wanna_print=False)
        return bool(ack_received)

    def set_gimbal_angles(self, pitch: float, yaw: float,
            pitch_rate: float = 0.0, yaw_rate: float = 0.0,
            lock_pitch: bool = True, lock_yaw: bool = True,
            yaw_in_earth_frame: bool = True,
            timeout_ack: float = 3.0
        ) -> bool:
        """Oriente le gimbal.

        Args:
            pitch (float): angle de tangage (rad).
            yaw (float): angle de lacet (rad).
            pitch_rate (float): vitesse de rotation en pitch (rad/s).
            yaw_rate (float): vitesse de rotation en yaw (rad/s).
            lock_pitch (bool): True = verrouille le pitch par rapport à l'horizon.
            lock_yaw (bool): True = verrouille le yaw par rapport au Nord (earth frame).
            yaw_in_earth_frame (bool): True = yaw exprimé dans le repère Terre, sinon véhicule
            timeout_ack (float): délai max d'attente pour l'ACK (secondes)

        Returns:
            bool: True si ACK reçu (commande acceptée), False sinon.
        """
        self.logger.log("[INFO] Sending gimbal command...", wanna_print=False)

        # Construction du flag bitmask
        flags = 0
        # Roll lock est souvent par défaut activé sur les gimbals stabilisés
        flags |= mavutil.mavlink.GIMBAL_MANAGER_FLAGS_ROLL_LOCK
        if lock_pitch:
            flags |= mavutil.mavlink.GIMBAL_MANAGER_FLAGS_PITCH_LOCK
        if lock_yaw:
            flags |= mavutil.mavlink.GIMBAL_MANAGER_FLAGS_YAW_LOCK
        # Choix du référentiel pour le yaw
        if yaw_in_earth_frame:
            flags |= mavutil.mavlink.GIMBAL_MANAGER_FLAGS_YAW_IN_EARTH_FRAME
        else:
            flags |= mavutil.mavlink.GIMBAL_MANAGER_FLAGS_YAW_IN_VEHICLE_FRAME

        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_DO_GIMBAL_MANAGER_PITCHYAW,
            1,pitch,yaw,pitch_rate,yaw_rate,    # Vitesses (rad/s)
            flags,0,0
        )

        ack_received = self.wait_command_ack(
            command=mavutil.mavlink.MAV_CMD_DO_GIMBAL_MANAGER_PITCHYAW,
            timeout=timeout_ack
        )
        if ack_received:
            self.logger.log("[SUCCESS] Gimbal orientation successfully set", wanna_print=False)
        else:
            self.logger.log("[FAIL] Gimbal orientation command failed", wanna_print=False)
        return bool(ack_received)
    
    def set_gimbal_retract(self, timeout_ack: float = 3.0) -> bool:
        """Met la gimbal en position retract (no stabilization).

        Args:
            timeout_ack (float): délai max d'attente pour l'ACK (secondes)

        Returns:
            bool: True si ACK reçu (commande acceptée), False sinon.
        """
        self.logger.log("[INFO] Sending gimbal retract command...")

        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_DO_GIMBAL_MANAGER_PITCHYAW,
            1,0,0,0,0,
            mavutil.mavlink.GIMBAL_MANAGER_FLAGS_RETRACT,0,0
        )

        ack_received = self.wait_command_ack(
            command=mavutil.mavlink.MAV_CMD_DO_GIMBAL_MANAGER_PITCHYAW,
            timeout=timeout_ack
        )
        if ack_received:
            self.logger.log("[SUCCESS] Gimbal retract successfully set")
        else:
            self.logger.log("[FAIL] Gimbal retract failed or timed out")
        return bool(ack_received)

    def set_gimbal_neutral(self, timeout_ack: float = 3.0) -> bool:
        """Met la gimbal en position neutral (roll=pitch=yaw=0).

        Args:
            timeout_ack (float): délai max d'attente pour l'ACK (secondes)

        Returns:
            bool: True si ACK reçu (commande acceptée), False sinon.
        """
        self.logger.log("[INFO] Sending gimbal neutral command...")

        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_DO_GIMBAL_MANAGER_PITCHYAW,
            1,0,0,0,0,
            mavutil.mavlink.GIMBAL_MANAGER_FLAGS_NEUTRAL,0,0
        )

        ack_received = self.wait_command_ack(
            mavutil.mavlink.MAV_CMD_DO_GIMBAL_MANAGER_PITCHYAW,
            timeout=timeout_ack
        )
        if ack_received:
            self.logger.log("[SUCCESS] Gimbal neutral successfully set")
        else:
            self.logger.log("[FAIL] Gimbal neutral failed")
        return bool(ack_received)

    def request_home_position(self,
            target_system: int | None = None,
            timeout_ack: float | None = 2,
            timeout_home_reception: float | None = 2
        ) -> tuple[float, float, float]:
        """Demande et attend de recevoir la position HOME.

        Args:
            target_system (int | None): ID MAVLink cible de la demande. Par défaut, vaut celui du master.
            timeout_ack (float | None): Timeout d'attente d'ack. 0 si pas d'attente (renvoie NaN, NaN, NaN). None si pas de timeout.
            timeout_home_reception (float | None): Timeout d'attente de réception de la position HOME. 0 si pas d'attente après ack (renvoie NaN, NaN, NaN). None si pas de timeout.

        Returns:
            tuple:
                - **latitude_home** (*float*) – Latitude HOME. NaN si pas de donnée reçue.
                - **longitude_home** (*float*) – Longitude HOME. NaN si pas de donnée reçue.
                - **altitude_home** (*float*) – Altitude HOME (MSL). NaN si pas de donnée reçue.
        """
        if self.fin_mission:
            self.logger.log("[FAIL] Mission stopped: Impossible to request HOME")
            return float('NaN'), float('NaN'), float('NaN')
        
        if target_system is None:
            target_system = self.master.target_system
        
        self.logger.log(f"[INFO] Requesting HOME to {target_system}")
        self.master.mav.command_long_send(
            target_system, # target_system
            mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1, # target_component
            mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE, # Commande pour demander un message
            1, # confirmation
            242, # param1 (Message ID)
            0,0,0,0,0,0 # param2-7 (unused)
        )
        
        accepted = self.wait_command_ack(
            command=mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE,
            source_system=target_system,
            timeout=timeout_ack
        )
        if not accepted:
            self.logger.log("[FAIL] Impossible to obtain HOME")
            return float('NaN'), float('NaN'), float('NaN')
        
        lat_home, lon_home, alt_home = self.wait_for_home(
            source_system=target_system,
            timeout=timeout_home_reception
        )
        if isnan(lat_home) and isnan(lon_home) and isnan(alt_home):
            self.logger.log("[FAIL] Impossible to receive HOME")
        return lat_home, lon_home, alt_home

    def send_timesync(self) -> None:
        """Envoie un TIMESYNC en broadcast pour obtenir les latences de connexion"""
        if self.fin_mission:
            self.logger.log("[FAIL] Mission stopped: Impossible to send TIMESYNC", wanna_print=False)
            return
        self.logger.log("[INFO] Sending TIMESYNC", wanna_print=False)
        self.timesync_handler.send_timesync()

    def set_msg_rate(self,
            msg_type: str | int,
            rate: float,
            target_system: int | None = None,
            timeout_ack: float | None = 2
        ) -> bool:
        """Change la fréquence d'envoi d'un certain type de message du contrôleur de vol.

        Args:
            msg_type (str | int): Type de message (nom ou ID).
            rate (float): Fréquence de transmission en Hz.
            target_system (int | None): ID MAVLink cible. Par défaut, vaut celui du master.
            timeout_ack (float | None): Timeout d'attente d'ack. 0 si pas d'attente (renvoie False). None si pas de timeout.

        Returns:
            bool: True si la requête a été acceptée par le contrôleur de vol, False sinon.
        """
        if self.fin_mission:
            self.logger.log("[FAIL] Mission stopped: Impossible to set msg rate")
            return False

        if rate <= 0:
            self.logger.log(f"[FAIL] Rate: {rate} must be superior to 0")
            return False

        if target_system is None:
            target_system = self.master.target_system
        
        # Recherche de l'ID du message
        if isinstance(msg_type, str):
            msg_id = getattr(mavutil.mavlink, f"MAVLINK_MSG_ID_{msg_type}", float('NaN'))
            if isnan(msg_id):
                self.logger.log(f"[FAIL] Wrong Msg Type: {msg_type}")
                return False
        else:
            msg_id = msg_type

        self.logger.log(f"[INFO] Sending msg rate request to {target_system}. Msg Type: {msg_type}, Rate: {rate}", wanna_print=False)
        self.master.mav.command_long_send(
            target_system, # target_system
            0, # target_component
            mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, # command
            1, # confirmation
            msg_id, # param1 (Message ID)
            int(10**6/rate), # param2 (Interval)
            0,0,0,0,0 # param3-7 (unused)
        )

        request_accepted = self.wait_command_ack(
            command=mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
            source_system=target_system,
            timeout=timeout_ack
        )
        if request_accepted:
            self.logger.log("[SUCCESS] Msg rate accepted", wanna_print=False)
        else:
            self.logger.log("[FAIL] Msg rate not accepted", wanna_print=False)
        return bool(request_accepted)

    def arm(self,
            force: bool = False,
            timeout_ack: float | None = 2,
            timeout_arming: float | None = 4,
            target_system: int | None = None
        ) -> bool:
        """Arme le drone.

        Args:
            force (bool): Armement forcé ou non.
            timeout_ack (float | None): Timeout d'attente d'ack. 0 si pas d'attente (renvoie False). None si pas de timeout.
            timeout_arming (float | None): Timeout d'attente d'armement. 0 si pas d'attente après ack (renvoie le résultat de l'attente d'ack en bool). None si pas de timeout.
            target_system (int | None): ID MAVLink cible. Par défaut, vaut celui du master.

        Returns:
            bool: Si le drone a été armé ou non.
        """
        if self.fin_mission:
            self.logger.log("[FAIL] Mission stopped: Impossible to arm")
            return False

        if not self.allow_actions:
            self.logger.log("[FAIL] Actions not allowed: Impossible to arm")
            return False

        if target_system is None:
            target_system = self.master.target_system

        if self.motors_armed(source_system=target_system):
            self.logger.log("[INFO] Vehicle already armed: arming process stopped")
            return True

        # Vérification du mode de vol actuel
        custom_mode = self.mode(source_system=target_system)
        if custom_mode in ["INITIALIZING", "PREFLIGHT", "CALIBRATION"]:
            self.logger.log("[FAIL] Initializing: impossible to arm")
            return False

        if self.autopilot_int(source_system=target_system) == mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA:
            if custom_mode in ["LAND", "TEST", "FOLLOW", "RTL", "FLOWHOLD", "BRAKE", "CIRCLE", "SMART_RTL", "SMARTRTL", "AUTO"]:
                self.logger.log(f"[WARNING] Mode {custom_mode} not armable: tying to change mode to GUIDED")
                mod_changed = self.change_mode(
                    mode="GUIDED",
                    target_system=target_system,
                    timeout_ack=3,
                    timeout_change_mode=5
                )
                if not mod_changed:
                    self.logger.log("[FAIL] Not the right mode, impossible to arm")
                    return False
        else:
            self.logger.log("[INFO] Vérification du mode avant armement non implémentée hors ArduPilot", wanna_print=False)

        # Demande d'armement
        self.logger.log(f"[INFO] Sending arm request to {target_system}")
        self.master.mav.command_long_send(
            target_system, # target_system
            mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1, # target_component
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, # command
            1, # confirmation
            1, # param1 (Arm)
            21196 if force else 0, # param2 (Force)
            0,0,0,0,0 # param3-7 (unused)
        )

        accepted = self.wait_command_ack(
            command=mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            timeout=timeout_ack,
            source_system=target_system
        )

        if not accepted:
            self.logger.log("[FAIL] Vehicle not armed (no ACK)")
            return False

        if timeout_arming == 0:
            self.logger.log("[WARNING] Vehicle sent an ACK but isn't armed yet")
            return True

        armed = self.wait_motors_armed(
            source_system=target_system,
            timeout=timeout_arming
        )
        if armed:
            self.logger.log("[SUCCESS] Vehicle armed")
        else:
            self.logger.log("[FAIL] Vehicle not armed")
        return bool(armed)

    def disarm(self,
            force: bool = False,
            timeout_ack: float | None = 2,
            timeout_disarming: float | None = 4,
            target_system: int | None = None
        ) -> bool:
        """Désarme le drone.

        Args:
            force (bool): Désarmement forcé ou non.
            timeout_ack (float | None): Timeout d'attente d'ack. 0 si pas d'attente (renvoie False). None si pas de timeout.
            timeout_disarming (float | None): Timeout d'attente de désarmement. 0 si pas d'attente après ack (renvoie le résultat de l'attente d'ack en bool). None si pas de timeout.
            target_system (int | None): ID MAVLink cible. Par défaut, vaut celui du master.

        Returns:
            bool: Si le drone a été armé ou non.
        """
        if self.fin_mission:
            self.logger.log("[FAIL] Mission stopped: Impossible to disarm")
            return False

        if not self.allow_actions:
            self.logger.log("[FAIL] Actions not allowed: Impossible to disarm")
            return False

        if target_system is None:
            target_system = self.master.target_system

        self.logger.log(f"[INFO] Sending disarm request to {target_system}")
        self.master.mav.command_long_send(
            target_system, # target_system
            mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1, # target_component
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, # command
            1, # confirmation
            0, # param1 (Disarm)
            21196 if force else 0, # param2 (Force)
            0,0,0,0,0 # param3-7 (unused)
        )

        accepted = self.wait_command_ack(
            command=mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            timeout=timeout_ack,
            source_system=target_system
        )

        if not accepted:
            self.logger.log("[FAIL] Vehicle not disarmed (no ACK)")
            return False

        if timeout_disarming == 0:
            self.logger.log("[WARNING] Vehicle sent an ACK but isn't disarmed yet")
            return True

        disarmed = self.wait_motors_disarmed(
            source_system=target_system,
            timeout=timeout_disarming
        )
        if disarmed:
            self.logger.log("[SUCCESS] Vehicle disarmed")
        else:
            self.logger.log("[FAIL] Vehicle not disarmed")
        return bool(disarmed)

    def change_mode(self,
            mode: str | int | tuple[int, int, int],
            timeout_ack: float | None = 2,
            timeout_change_mode: float | None = 4,
            target_system: int | None = None
        ) -> bool:
        """Change le mode de vol.

        Args:
            mode (str | int | tuple[int, int, int]): Mode de vol. str: nom du mode. int: ID du mode sur ArduPilot. tuple[int, int, int]: (MAV_MODE_FLAG, Custom Main Mode, Custom Sub Mode) sur PX4.
            timeout_ack (float | None): Timeout d'attente d'ack. 0 si pas d'attente (renvoie False). None si pas de timeout.
            timeout_change_mode (float | None): Timeout d'attente de changement de mode. 0 si pas d'attente (renvoie le résultat de l'attente d'ack en bool). None si pas de timeout.
            target_system (int | None): ID MAVLink cible. Par défaut, vaut celui du master.

        Returns:
            bool: Si le mode a changé ou non.
        """
        if self.fin_mission:
            self.logger.log("[FAIL] Mission stopped: Impossible to change mode")
            return False

        if not self.allow_actions:
            self.logger.log("[FAIL] Actions not allowed: Impossible to change mode")
            return False

        if target_system is None:
            target_system = self.master.target_system

        # Recherche des IDs associés au mode de vol str
        if isinstance(mode, str):
            mode_mapping = self.mode_mapping(source_system=target_system)
            if mode_mapping is not None and mode in mode_mapping:
                key = mode_mapping[mode]
            else:
                self.logger.log(f"[FAIL] Trying to change mode. Unknow mode {mode}")
                self.logger.log(f"[LOG] mode_mapping({target_system}): {mode_mapping}", wanna_print=False)
                return False
        else:
            key = mode

        # Décomposition des IDs
        if isinstance(key, int):
            base_mode = mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED
            custom_main_mode = key
            custom_sub_mode = 0
        elif isinstance(key, tuple):
            if len(key) != 3:
                self.logger.log(f"[FAIL] Trying to change mode. Invalid mode: {key}")
                return False
            base_mode = key[0]
            custom_main_mode = key[1]
            custom_sub_mode = key[2]
        else:
            self.logger.log(f"[FAIL] Trying to change mode. Invalid mode: {key}")
            return False

        self.logger.log(f"[INFO] Sending change mode request to {target_system}: {mode}")
        self.master.mav.command_long_send(
            target_system, # target_system
            mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1, # target_component
            mavutil.mavlink.MAV_CMD_DO_SET_MODE, # command
            1, # confirmation
            base_mode, # param1 (Mode)
            custom_main_mode, # param2 (Custom Mode)
            custom_sub_mode, # 3 (Custom Submode)
            0,0,0,0  # param4-7 (unused)
        )

        accepted = self.wait_command_ack(
            command=mavutil.mavlink.MAV_CMD_DO_SET_MODE,
            timeout=timeout_ack,
            source_system=target_system
        )

        if not accepted:
            self.logger.log("[FAIL] Mod not changed (no ACK)")
            return False

        if timeout_change_mode == 0:
            self.logger.log("[WARNING] Vehicle sent an ACK but mode isn't changed yet")
            return True

        mod_changed = self.wait_mode_changed(
            mode=mode,
            source_system=target_system,
            timeout=timeout_change_mode
        )

        if mod_changed:
            self.logger.log("[SUCCESS] Mod changed")
        else:
            self.logger.log("[FAIL] Mod not changed")
        return bool(mod_changed)

    def goto(self,
            latitude: float,
            longitude: float,
            relative_altitude: float,
            target_system: int | None = None
        ) -> None:
        """Envoie une requête pour aller à un point GPS.

        Args:
            latitude (float): Latitude (deg).
            longitude (float): Longitude (deg).
            relative_altitude (float): Altitude relative (m).
            target_system (int | None): ID MAVLink cible. Par défaut, vaut celui du master.
        """
        if self.fin_mission:
            self.logger.log("[FAIL] Mission stopped: Impossible to send a goto")
            return False

        if not self.allow_actions:
            self.logger.log("[FAIL] Actions not allowed: Impossible to send a goto")
            return False

        if target_system is None:
            target_system = self.master.target_system

        self.logger.log(f"[INFO] Sending goto to {target_system}..", wanna_print=False)
        self.master.mav.set_position_target_global_int_send(
            self.time_boot_ms, # time_boot_ms
            target_system, # target_system
            mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1, # target_component
            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT, # coordinate_frame
            0b0000111111111000, # type_mask
            int(latitude * 1e7), # lat_int
            int(longitude * 1e7), # lon_int
            relative_altitude, # relative_alt
            0,0,0, # vx, vy, vz
            0,0,0, # afx, afy, afz
            0,0 # yaw, yaw_rate
        )

    def set_speed(self,
            vx: float,
            vy: float,
            vz: float,
            yaw: int | None = None,
            target_system: int | None = None
        ) -> None:
        """Impose la vitesse du drone.

        Args:
            vx (float): Vitesse vers le Nod en m/s.
            vy (float): Vitesse vers l'Est en m/s.
            vz (float): Vitesse vers le bas en m/s.
            yaw (int | None): Yaw à atteindre. Pas défini par défaut.
            target_systel (int | None): ID MAVLink cible. Par défaut, vaut celui du master.
        """
        if self.fin_mission:
            self.logger.log("[FAIL] Mission stopped: Impossible to set speed")
            return False

        if not self.allow_actions:
            self.logger.log("[FAIL] Actions not allowed: Impossible to set speed")
            return False

        if target_system is None:
            target_system = self.master.target_system
        if yaw is None:
            bitmask = 0b0000111111000111
        else:
            bitmask = 0b0000101111000111
        self.logger.log(f"[INFO] Sending set speed request to {target_system}..", wanna_print=False)
        self.master.mav.set_position_target_local_ned_send(
            self.time_boot_ms, # time_boot_ms
            target_system, # target_system
            mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1, # target_component
            mavutil.mavlink.MAV_FRAME_LOCAL_OFFSET_NED, # coordinate_frame
            bitmask, # type_mask
            0,0,0, # x, y, z
            vx, vy, vz, # vx, vy, vz
            0,0,0, # afx, afy, afz
            yaw if yaw is not None else 0,0 # yaw, yaw_rate
        )

    def takeoff(self,
            altitude: float,
            pitch: float = 0,
            timeout_ack: float | None = 2,
            timeout_takeoff: float | None = None,
            precision: float = 1,
            target_system: int | None = None
        ) -> bool:
        """Fais un takeoff. Bien penser à armer le drone en amont.

        Args:
            altitude (float): Altitude de takeoff.
            pitch (float): Pitch imposé.
            timeout_ack (float | None): Timeout d'attente d'ack. 0 si pas d'attente (renvoie False). None si pas de timeout.
            timeout_takeoff (float | None): Timeout d'attente de réalisation de takeoff. 0 si pas d'attente (renvoie le résultat de l'attente d'ack en bool). None si pas de timeout.
            precision (float): Précision à atteindre en m pour considérer le takeoff réussi. Defaults to 1.
            target_system (int | None): ID MAVLink cible. Par défaut, vaut celui du master.

        Returns:
            bool: Résultat du takeoff.
        """
        if self.fin_mission:
            self.logger.log("[FAIL] Mission stopped: Impossible to takeoff")
            return False

        if not self.allow_actions:
            self.logger.log("[FAIL] Actions not allowed: Impossible to takeoff")
            return False

        if target_system is None:
            target_system = self.master.target_system

        # Recherche du bon mode de vol
        if self.autopilot_int(source_system=target_system) == mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA:
            if self.mode(source_system=target_system) != "GUIDED":
                self.logger.log(f"[WARNING] Mode {self.mode(source_system=target_system)} != GUIDED")
                mod_changed = self.change_mode(
                    mode="GUIDED",
                    timeout_ack=3,
                    timeout_change_mode=5,
                    target_system=target_system
                )
                if not mod_changed:
                    self.logger.log("[FAIL] Takeoff aborted")
                    return False
        else:
            self.logger.log("[INFO] Pas de vérification du mode: appareil n'étant pas sur ArduPilot", wanna_print=False)

        m = self.get_msg(
            msg_type="EXTENDED_SYS_STATE",
            source_system=target_system
        )
        if pitch==0 and m and (m.landed_state == mavutil.mavlink.MAV_LANDED_STATE_IN_AIR or m.landed_state == mavutil.mavlink.MAV_LANDED_STATE_TAKEOFF): # Si on est en l'air ou en train de takeoff déjà
            # On veut pitch==0 car on envoie un goto vers le haut
            self.logger.log("[INFO] Vehicle already in air: sending goto request instead of normal takeoff..")
            current_lat, current_lon, _, _ = self.position(source_system=target_system)
            self.master.mav.set_position_target_global_int_send(
                self.time_boot_ms, # time_boot_ms
                target_system, # target_system
                mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1, # target_component
                mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT, # coordinate_frame
                0b0000111111111000, # type_mask
                int(current_lat * 1e7), # lat_int
                int(current_lon * 1e7), # lon_int
                altitude, # relative_alt
                0,0,0, # vx, vy, vz
                0,0,0, # afx, afy, afz
                0,0 # yaw, yaw_rate
            )

        else:
            self.logger.log(f"[INFO] Sending takeoff request to {target_system}: (alt, pitch): {altitude, pitch}..")
            self.master.mav.command_long_send(
                target_system, # target_system
                mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1, # target_component
                mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, # command
                1, # confirmation
                pitch, # param1 (Pitch)
                0,0, # params2-3 (unused)
                0, #param4 (Yaw)
                0, # param5 (Latitude)
                0, # param6 (Longitude)
                altitude # param7 (Altitude)
            )

            accepted = self.wait_command_ack(
                command=mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                timeout=timeout_ack, source_system=target_system
            )
            if not accepted:
                self.logger.log("[FAIL] Takeoff failed (no ACK)")
                return False

        _, _, relative_alt, _ = self.position(source_system=target_system)
        if abs(relative_alt - altitude) < precision:
            self.logger.log("[SUCCESS] Takeoff succeded")
            return True

        if timeout_takeoff == 0:
            self.logger.log("[WARNING] Vehicle accepted the takeoff but hasn't takeoff yet")
            return True

        goto_sent = False

        # Attente du bon positionnement
        start_time = time.time()
        while True:
            if self.fin_mission:
                self.logger.log("[FAIL] Mission stopped: stop waiting for takeoff end")
                return False

            _, _, relative_alt, _ = self.position(source_system=target_system)
            if abs(relative_alt - altitude) < precision:
                self.logger.log("[SUCCESS] Altitude reached: stop waiting for takeoff end")
                return True

            if not goto_sent:
                if not self.fin_mission and self.allow_actions:
                    m = self.get_msg(
                        msg_type="EXTENDED_SYS_STATE",
                        source_system=target_system
                    )
                    # pitch==0 : indique que c'est un drone, MAV_LANDED_STATE_IN_AIR : takeoff terminé
                    if pitch==0 and m and m.landed_state == mavutil.mavlink.MAV_LANDED_STATE_IN_AIR:
                        self.logger.log(f"[INFO] Sending goto request repositioning to {target_system}. alt: {altitude}..")
                        current_lat, current_lon, _, _ = self.position(source_system=target_system)
                        self.master.mav.set_position_target_global_int_send(
                            self.time_boot_ms, # time_boot_ms
                            target_system, # target_system
                            mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1, # target_component
                            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT, # coordinate_frame
                            0b0000111111111000, # type_mask
                            int(current_lat * 1e7), # lat_int
                            int(current_lon * 1e7), # lon_int
                            altitude, # relative_alt
                            0,0,0, # vx, vy, vz
                            0,0,0, # afx, afy, afz
                            0,0 # yaw, yaw_rate
                        )
                        goto_sent = True

            if timeout_takeoff is not None and start_time + timeout_takeoff < time.time():
                self.logger.log("[FAIL] Timeout: stop waiting for takeoff end")
                return False

            time.sleep(0.05)

    def land(self,
            timeout_ack: float | None = 2,
            timeout_change_mode: float | None = 3,
            timeout_land: float | None = None,
            target_system: int | None = None
        ) -> bool:
        """Fais un simple landing. Implémenté seulement sur ArduPilot pour l'instant.

        Args:
            timeout_ack (float | None): Timeout d'attente d'ack.
            timeout_change_mode (float | None): Timeout d'attente de changement de mode.
            timeout_land (float | None): Timeout d'attente d'atterissage.
            target_system (int | None): ID MAVLink cible. Par défaut, vaut celui du master.

        Returns:
            bool: Résultat de l'opération.
        """
        if self.fin_mission:
            self.logger.log("[FAIL] Mission stopped: Impossible to land")
            return False

        if not self.allow_actions:
            self.logger.log("[FAIL] Actions not allowed: Impossible to land")
            return False

        if self.autopilot_int(source_system=target_system) != mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA:
            self.logger.log("[FAIL] Landing non implémenté hors ArduPilot")
            return False

        if not self.change_mode(
            mode="LAND",
            timeout_ack=timeout_ack,
            timeout_change_mode=timeout_change_mode,
            target_system=target_system
        ):
            self.logger.log("[FAIL] Landing failed")
            return False

        disarmed = self.wait_motors_disarmed(
            source_system=target_system,
            timeout=timeout_land
        )
        if disarmed:
            self.logger.log("[SUCCESS] Landing succeded")
        else:
            self.logger.log("[FAIL] Landing failed")
        return bool(disarmed)

    def write_parameter(self,
            parameter: str, value,
            param_type: int,
            target_system: int | None = None
        ):
        """Change un des paramètres du contrôleur de vol.

        Args:
            parameter (str): Nom du paramètre.
            value: Valeur du paramètre.
            param_type (int): MAV_PARAM_TYPE | Type de paramètre.
            target_system (int | None): ID MAVLink cible. Par défaut, vaut celui du master.
        """
        # Pour connaitre le param_type associé, demander à ChatGPT, ça marche bien
        # Attention, certains paramètres nécessitent le reboot pour fonctionner (regarder sur Mission Planner quand vous changez à la main)
        if self.fin_mission:
            self.logger.log("[FAIL] Mission stopped: Impossible to write parameter")
            return False

        if not self.allow_actions:
            self.logger.log("[FAIL] Actions not allowed: Impossible to write parameter")
            return False

        if target_system is None:
            target_system = self.master.target_system
        self.logger.log(f"[INFO] Sending writing parameter request to {target_system}..", wanna_print=False)
        self.master.mav.param_set_send(
            target_system, # target_system
            mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1, # target_component
            parameter.encode(), # param_id
            value, # param_value
            param_type # param_type
        )

    def send_waypoint(self,
            waypoint_index: int,
            frame: int = mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
            command: int = mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
            param1: float = 0.0,
            param2: float = 0.0,
            param3: float = 0.0,
            param4: float = 0.0,
            x: float = 0.0,
            y: float = 0.0,
            z: float = 0.0,
            target_system: int | None = None
        ) -> None:
        """Envoie un waypoint.

        Args:
            waypoint_index (int): Waypoint ID (sequence number). Commence à zéro. Augmente pour chaque waypoint, pas de trou dans la séquence (0,1,2,3,4).
            frame (int): MAV_FRAME | Système de coordonnées du waypoint.
            command (int): MAV_CMD | Action du waypoint.
            param1 (float): param1 (depending on command).
            param2 (float): param2 (depending on command).
            param3 (float): param3 (depending on command).
            param4 (float): param4 (depending on command).
            x (float): local: x position in meters, global: latitude in degrees.
            y (float): local: y position in meters, global: longitude in degrees.
            z (float): global: altitude in meters (relative or absolute, depending on frame).
            target_system (int): ID MAVLink cible. Par défaut, vaut celui du master.
        """
        if self.fin_mission:
            self.logger.log("[FAIL] Mission stopped: Impossible to send a waypoint")
            return False

        if not self.allow_actions:
            self.logger.log("[FAIL] Actions not allowed: Impossible to send a waypoint")
            return False

        if target_system is None:
            target_system = self.master.target_system
        if frame in [
            mavutil.mavlink.MAV_FRAME_GLOBAL,
            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
            mavutil.mavlink.MAV_FRAME_GLOBAL_INT,
            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
            mavutil.mavlink.MAV_FRAME_GLOBAL_TERRAIN_ALT,
            mavutil.mavlink.MAV_FRAME_GLOBAL_TERRAIN_ALT_INT
            ]:
            x = x * 1e7
            y = y * 1e7
        elif frame in [
            mavutil.mavlink.MAV_FRAME_LOCAL_NED,
            mavutil.mavlink.MAV_FRAME_LOCAL_ENU,
            mavutil.mavlink.MAV_FRAME_LOCAL_OFFSET_NED,
            mavutil.mavlink.MAV_FRAME_LOCAL_FRD,
            mavutil.mavlink.MAV_FRAME_LOCAL_FLU,
            mavutil.mavlink.MAV_FRAME_BODY_NED,
            mavutil.mavlink.MAV_FRAME_BODY_OFFSET_NED,
            mavutil.mavlink.MAV_FRAME_BODY_FRD
            ]:
            x = x * 1e4
            y = y * 1e4
        self.logger.log(f"[INFO] Sending waypoint {waypoint_index}")
        self.master.mav.mission_item_int_send(
            target_system, # target_system
            mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1, # target_component
            waypoint_index, # seq
            frame, # frame
            command, # command
            0, # current
            1, # autocontinue
            param1, # param1
            param2, # param2
            param3, # param3
            param4, # param4
            int(x), # x
            int(y), # y
            z # z
        )

    def send_first_waypoint(self,
            target_system: int | None = None,
            timeout: float | None = 2,
            timeout_ack: float | None = 2
        ) -> bool:
        """Envoie le waypoint secret (seq=0) sur ArduPilot.

        Args:
            target_system (int): ID MAVLink cible. Par défaut, vaut celui du master.
            timeout (float | None): Timeout d'attente (si pas envoi auto de home request).
            timeout_ack (float | None): Timeout d'attente d'ack (si pas envoi auto de home request).

        Returns:
            bool: Si le waypoint a été envoyé ou pas.
        """
        if self.fin_mission:
            self.logger.log("[FAIL] Mission stopped: Impossible to send first waypoint")
            return False

        if not self.allow_actions:
            self.logger.log("[FAIL] Actions not allowed: Impossible to send first waypoint")
            return False

        if not self._send_automatic_home_request:
            home_lat, home_lon, home_alt = self.request_home_position(target_system=target_system, timeout_ack=timeout_ack, timeout_home_reception=timeout)
            if isnan(home_lat) and isnan(home_lon) and isnan(home_alt):
                self.logger.log("[FAIL] No HOME position received: Impossible to send first waypoint")
                return False
        else:
            home_lat, home_lon, home_alt = self.home_position(source_system=target_system)
            if isnan(home_lat) and isnan(home_lon) and isnan(home_alt):
                self.logger.log("[FAIL] No HOME position received: Impossible to send first waypoint")
                return False
        self.send_waypoint(
            waypoint_index=0,
            frame=mavutil.mavlink.MAV_FRAME_GLOBAL,
            x=home_lat,
            y=home_lon,
            z=home_alt
        )
        return True

    def send_waypoint_count(self,
            number_waypoints: int,
            target_system: int | None = None
        ) -> None:
        """Indique au contrôleur de vol le nombre de waypoints qu'on va lui envoyer.
        A envoyer avant chaque mission.
        Ne pas oublier le 1er waypoint sur ArduPilot.

        Args:
            number_waypoints (int): Nombre de waypoints.
            target_system (int): ID MAVLink cible.
        """
        if self.fin_mission or not self.allow_actions:
            return

        if target_system is None:
            target_system = self.master.target_system
        self.logger.log(f"[INFO] Sending waypoint count: {number_waypoints}")
        self.master.mav.mission_count_send(
            target_system, # target_system
            mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1, # target_component
            number_waypoints # count
        )

    def clear_waypoints(self,
            timeout: float | None = 2,
            target_system: int | None = None
        ) -> bool:
        """Supprime tout les waypoints.

        Args:
            timeout (float | None): Timeout d'attente d'ack.
            target_system (int | None): ID MAVLink cible. Par défaut, vaut celui du master.

        Returns:
            bool: Résultat de la requête.
        """
        if self.fin_mission:
            self.logger.log("[FAIL] Mission stopped: Impossible to clear waypoints")
            return False

        if not self.allow_actions:
            self.logger.log("[FAIL] Actions not allowed: Impossible to clear waypoints")
            return False

        if target_system is None:
            target_system = self.master.target_system
        self.logger.log(f"[INFO] Sending waypoint clear request to {target_system}")
        self.master.mav.mission_clear_all_send(
            target_system, # target_system
            mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1 # target_component
        )

        return self.wait_mission_ack(
            mission_type=mavutil.mavlink.MAV_MISSION_TYPE_MISSION,
            timeout=timeout,
            source_system=target_system
        )

    def start_mission(self,
            first_wp_tkoff: bool,
            target_system: int | None = None,
            timeout: float | None = 3
        ) -> bool:
        """Commence la mission. Implémenté seulement sur ArduPilot pour l'instant.

        Args:
            first_wp_tkoff (bool): True si le 1er wp est un wp de takeoff, False sinon.
            target_system (int | None): ID MAVLink cible. Par défaut, vaut celui du master.
            timeout (float | None): Timeout d'attente (un peu utilisé partout).

        Returns:
            bool: Si la mission a commencée ou non.
        """
        if self.fin_mission:
            self.logger.log("[FAIL] Mission stopped: Impossible to start misison")
            return False

        if not self.allow_actions:
            self.logger.log("[FAIL] Actions not allowed: Impossible to start mission")
            return False

        if self.autopilot_int(source_system=target_system) != mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA:
            self.logger.log("[FAIL] Start mission: Fonctionnalité non implémentée hors ArduPilot")
            return False

        if target_system is None:
            target_system = self.master.target_system
        if first_wp_tkoff:
            armed = self.arm(
                timeout_ack=timeout,
                timeout_arming=timeout,
                target_system=target_system
            )
            if not armed:
                self.logger.log("[FAIL] Start mission failed")
                return False
            mod_auto = self.change_mode(
                mode="AUTO",
                timeout_ack=timeout,
                timeout_change_mode=timeout,
                target_system=target_system
            )
            if not mod_auto:
                self.logger.log("[FAIL] Start mission failed")
                return False
            self.logger.log("[SUCCESS] Mission started")
            return True
        disarmed = self.disarm(
            timeout_ack=timeout,
            timeout_disarming=timeout,
            target_system=target_system
        )
        if not disarmed:
            self.logger.log("[FAIL] Start mission failed")
            return False
        mod_auto = self.change_mode(
            mode="AUTO",
            timeout_ack=timeout,
            timeout_change_mode=timeout,
            target_system=target_system
        )
        if not mod_auto:
            self.logger.log("[FAIL] Start misison failed")
            return False
        self.master.mav.command_long_send(
            target_system, # target_system
            mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1, # target_component
            mavutil.mavlink.MAV_CMD_MISSION_START, # command
            1, # confirmation
            1, # param1 (First Item)
            0, # param2 (Last Item) (à confirmer)
            0,0,0,0,0 # param3-7 (unused)
        )
        ack = self.wait_command_ack(
            command=mavutil.mavlink.MAV_CMD_MISSION_START,
            source_system=target_system,
            timeout=timeout
        )
        if ack:
            self.logger.log("[SUCCESS] Mission Started")
        else:
            self.logger.log("[FAIL] Start mission failed")
        return bool(ack)

    def return_to_launch(self,
            timeout: float | None = 2,
            target_system: int | None = None
        ) -> bool:
        """Envoie une demande de RTL.

        Args:
            timeout (float | None): Timeout d'attente d'ack.
            target_system (int | None): ID MAVLink cible. Par défaut, vaut celui du master.

        Returns:
            bool: Résultat de la requête.
        """
        if self.fin_mission:
            self.logger.log("[FAIL] Mission stopped: Impossible to RTL")
            return False

        if not self.allow_actions:
            self.logger.log("[FAIL] Actions not allowed: Impossible to RTL")
            return False

        if target_system is None:
            target_system = self.master.target_system
        self.logger.log(f"[INFO] Sending RTL request to {target_system}")
        self.master.mav.command_long_send(
            target_system, # target_system
            mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1, # target_component
            mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH, # command
            1, # confirmation
            0,0,0,0,0,0,0 # param1-7 (unused)
        )

        accepted = self.wait_command_ack(
            command=mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
            timeout=timeout,
            source_system=target_system
        )
        if accepted:
            self.logger.log("[SUCCESS] RTL started")
        else:
            self.logger.log("[FAIL] RTL failed")
        return bool(accepted)

    def reboot(self,
            timeout_ack: float | None = 2,
            target_system: int | None = None,
            force=False
        ) -> bool:
        """Reboot l'autopilot.

        Args:
            timeout_ack (float | None): Timeout d'attente d'ack.
            target_system (int | None): ID MAVLink cible.
            force (bool): Indique si on veut faire un reboot force ou non (le faites pas svp, c'est pour la culture).

        Returns:
            bool: Résultat de l'opération.
        """
        if self.fin_mission:
            self.logger.log("[FAIL] Mission stopped: Impossible to reboot")
            return False

        if not self.allow_actions:
            self.logger.log("[FAIL] Actions not allowed: Impossible to reboot")
            return False

        if target_system is None:
            target_system = self.master.target_system
        self.logger.log(f"[INFO] Sending reboot request to {target_system}..")
        self.master.mav.command_long_send(
            target_system, # target_system
            mavutil.mavlink.MAV_COMP_ID_ALL, # target_component
            mavutil.mavlink.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN, # command
            1, # confirmation
            1, # param1 (Autopilot)
            0, # param2 (Companion)
            0, # param3 (Component action)
            0, # param4 (Component ID)
            0, # param5 (unused)
            20190226 if force else 0, # param6 (force)
            0 # param7 (unused)
        )

        accepted = self.wait_command_ack(
            command=mavutil.mavlink.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN,
            timeout=timeout_ack,
            source_system=target_system
        )
        if not accepted:
            self.logger.log("[FAIL] Reboot failed")
        else:
            self.logger.log("[SUCCESS] Reboot accepted")
        return bool(accepted)

    def do_follow_with_takeoff(self, target_system: int):
        """Suit un véhicule en mouvement (+ takeoff). Marche seulement sur ArduPilot.

        Args:
            target_system (int): ID MAVLink du véhicule à suivre.
        """
        if self.fin_mission:
            self.logger.log("[FAIL] Mission stopped: Impossible to follow")
            return False

        if not self.allow_actions:
            self.logger.log("[FAIL] Actions not allowed: Impossible to follow")
            return False

        if self.autopilot_int() != mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA:
            self.logger.log("[FAIL] Impossible de FOLLOW hors ArduPilot")
            return
        takeoff_succeded = self.takeoff(altitude=5)
        if not takeoff_succeded:
            return
        self.do_follow(target_system=target_system)

    def do_follow(self, target_system: int) -> None:
        """Suit un véhicule en mouvement. Marche seulement sur ArduPilot.

        Args:
            target_system (int): ID MAVLink du véhicule à suivre.
        """
        if self.fin_mission:
            self.logger.log("[FAIL] Mission stopped: Impossible to follow")
            return False

        if not self.allow_actions:
            self.logger.log("[FAIL] Actions not allowed: Impossible to follow")
            return False

        if self.autopilot_int() != mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA:
            self.logger.log("[FAIL] Impossible de FOLLOW hors ArduPilot")
            return
        self.logger.log("[INFO] Initializing FOLLOW..")

        rate = max(10, self._data_init["pos_rate"]) # On veut minimum 10 Hz
        self.set_msg_rate(
            msg_type="GLOBAL_POSITION_INT",
            rate=rate,
            target_system=target_system
        )
        self.set_msg_rate(
            msg_type="ATTITUDE_QUATERNION",
            rate=rate,
            target_system=target_system
        )
        self.set_msg_rate(
            msg_type="ATTITUDE",
            rate=rate,
            target_system=target_system
        )

        self.logger.log("[INFO] Waiting for GPS..")
        while self.get_msg(
            msg_type="GLOBAL_POSITION_INT",
            source_system=target_system
        ) is None:
            if self.fin_mission:
                self.logger.log("[FAIL] Mission stopped: follow stopped")
                return
            time.sleep(0.05)
        self.logger.log("[INFO] GPS received")

        if self.fin_mission:
            self.logger.log("[FAIL] Mission stopped: follow stopped")
            return

        mode_mapping = self.mode_mapping()
        if mode_mapping is None or "FOLLOW" not in mode_mapping:
            mode_id = 23 # Ne pas toucher, ça marche sur ArduCopter
        else:
            mode_id = mode_mapping["FOLLOW"]

        mod_changed = self.change_mode(mode=mode_id)
        if not mod_changed:
            self.logger.log("[FAIL] Mission stopped: Mode isn't FOLLOW")
            return

        self.logger.log("[SUCCESS] Follow started")

        while True:
            if self.fin_mission or not self.allow_actions:
                self.logger.log("[FAIL] Mission stopped: follow stopped")
                self.change_mode(mode="GUIDED")
                return
            if self.custom_mode() != mode_id:
                self.logger.log("[FAIL] Mode != FOLLOW: follow stopped")
                return

            global_position_int = self.get_msg(
                msg_type="GLOBAL_POSITION_INT",
                source_system=target_system
            )

            lat = global_position_int.lat
            lon = global_position_int.lon
            alt = global_position_int.alt / 1000
            vx = global_position_int.vx / 100
            vy = global_position_int.vy / 100
            vz = global_position_int.vz / 100

            est_capabilities = 1 | 2

            scaled_imu = self.get_msg(
                msg_type="SCALED_IMU",
                source_system=target_system
            )
            if scaled_imu is None:
                scaled_imu = self.get_msg(
                    msg_type="SCALED_IMU2",
                    source_system=target_system
                )
            if scaled_imu is None:
                scaled_imu = self.get_msg(
                    msg_type="SCALED_IMU3",
                    source_system=target_system
                )

            if scaled_imu:
                xacc = scaled_imu.xacc / 1000.0 * 9.80665
                yacc = scaled_imu.yacc / 1000.0 * 9.80665
                zacc = scaled_imu.zacc / 1000.0 * 9.80665
                est_capabilities = est_capabilities | 4
            else:
                xacc, yacc, zacc = 0, 0, 0

            attitude_quaternion = self.get_msg(
                msg_type="ATTITUDE_QUATERNION",
                source_system=target_system
            )
            attitude = self.get_msg(
                msg_type="ATTITUDE",
                source_system=target_system
            )

            if attitude_quaternion and attitude:
                q1 = attitude_quaternion.q1
                q2 = attitude_quaternion.q2
                q3 = attitude_quaternion.q3
                q4 = attitude_quaternion.q4
                rollspeed = attitude.rollspeed
                pitchspeed = attitude.pitchspeed
                yawspeed = attitude.yawspeed
                est_capabilities = est_capabilities | 8
            else:
                q1, q2, q3, q4 = 0, 0, 0, 0
                rollspeed, pitchspeed, yawspeed = 0, 0, 0

            self.master.mav.follow_target_send(
                self.time_boot_ms,  # timestamp (ms)
                est_capabilities,  # est_capabilities (en gros je lui dit qu'on envoie toutes les données)
                lat, # Latitude (WGS84) (degE7)
                lon, # Longitude (WGS84) (degE7)
                alt, # Altitude (MSL) (m)
                [vx, vy, vz], # vel (m/s)
                [xacc, yacc, zacc], # acc (m/s/s)
                [q1, q2, q3, q4], # attitude_q
                [rollspeed, pitchspeed, yawspeed], # rates
                [0, 0, 0], # position_cov
                0 # custom_state
            )
            time.sleep(0.1) # 10 Hz

    def send_thow_mode_config_request(self,
            value: int = 1,
            next_mode: str = "GUIDED",
            throw_mot_start: int = 0,
            target_system: int | None = None
        ) -> None:
        """Configure le throw mode (ArduPilot).

        Args:
            value (int): THROW_TYPE.
            next_mode (str): THROW_NEXTMODE.
            throw_mot_start (int): THROW_MOT_START.
            target_system (int | None): ID MAVLink cible. Par défaut, vaut celui du master.
        
        Notes:
            value = 1: Chute seule.
            value = 0: Montée puis chute.
            throw_mot_start = 0: Les moteurs ne tournent pas quand le drone est armé.
            throw_mot_start = 1: Les moteurs tournent quand le drone est armé.
        """
        if self.fin_mission:
            self.logger.log("[FAIL] Mission stopped: Impossible to RTL")
            return False

        if not self.allow_actions:
            self.logger.log("[FAIL] Actions not allowed: Impossible to RTL")
            return False

        if self.autopilot_int() != mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA:
            self.logger.log("[FAIL] Impossible de configurer le mode THROW hors ArduPilot")
            return
        if target_system is None:
            target_system = self.master.target_system
        self.logger.log(f"[INFO]Sending throw mode config: {target_system}")

        if next_mode == "AUTO":
            next_mode_id = 3
        elif next_mode=="GUIDED":
            next_mode_id=4
        elif next_mode=="LOITER":
            next_mode_id=5
        elif next_mode=="RTL":
            next_mode_id=6
        elif next_mode=="LAND":
            next_mode_id=9
        elif next_mode=="BRAKE":
            next_mode_id=17
        elif next_mode=="THROW":
            next_mode_id=18
        else:
            self.logger.log("[FAIL] Next mode not supported")
            return

        self.write_parameter(
            parameter="THROW_TYPE",
            value=value,
            param_type=mavutil.mavlink.MAV_PARAM_TYPE_UINT8
        )
        self.write_parameter(
            parameter="THROW_NEXTMODE",
            value=next_mode_id,
            param_type=mavutil.mavlink.MAV_PARAM_TYPE_INT32
        )
        self.write_parameter(
            parameter="THROW_MOT_START",
            value=throw_mot_start,
            param_type=mavutil.mavlink.MAV_PARAM_TYPE_UINT8
        )

    def send_landing_target(self, x: float, y: float, z: float) -> None:
        """Envoie une requête de landing target. Déplacements dans le repère du drone (BODY).

        Args:
            x (float): Front (+) / Back (-) (m)
            y (float): Right (+) / Left (-) (m)
            z (float): Down (+) / Up (-) (m)
        """
        if self.fin_mission:
            self.logger.log("[FAIL] Mission stopped: Impossible to send a landing target")
            return False

        if not self.allow_actions:
            self.logger.log("[FAIL] Actions not allowed: Impossible to send a landing target")
            return False

        self.logger.log("[INFO] Sending landing target..", wanna_print=False)
        if self.autopilot_int() == mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA:
            distance_m = sqrt(x**2+y**2+z**2)
        else:
            distance_m = 0
        self.master.mav.landing_target_send(
            self.time_usec, # time_usec
            0, # target_num
            mavutil.mavlink.MAV_FRAME_BODY_FRD, # frame
            0,0, #angle_x, angle_y (ignored)
            distance_m, # distance
            0,0, # size_x, size_y (ignored)
            x, y, z, # x, y, z
            [1, 0, 0, 0], # q
            mavutil.mavlink.LANDING_TARGET_TYPE_VISION_OTHER, # type
            1 # position_valid
        )

    # -------------
    # Communication
    # -------------

    def send_statustext(self,
            text: str,
            severity: int = 7,
            msg_id: int = 0
        ):
        """Envoie un STATUSTEXT.

        Args:
            text (str): Texte à envoyer.
            severity (int): Sévérité.
            id (int): ID du statustext.
        """
        if self.fin_mission:
            self.logger.log("[FAIL] Mission stopped: Impossible to send a STATUSTEXT")
            return False

        max_chunk_size = 50
        chunks = [text[i:i+max_chunk_size] for i in range(0, len(text), max_chunk_size)]

        if len(chunks) > 1:
            self.logger.log("[INFO] Statustext tronqué", wanna_print=False)

        self.logger.log(f"[INFO] Sending statustext: {text}", wanna_print=False)
        for i, chunk in enumerate(chunks):
            try:
                text_encoded = chunk.ljust(50, '\0').encode('ascii')
            except Exception:
                text_encoded = unicodedata.normalize('NFKD', chunk.ljust(50, '\0')).encode('ascii', 'ignore')
            self.master.mav.statustext_send(
                severity,
                text_encoded,
                msg_id,
                i
            )
            if i == len(chunk) - 1:
                break # On veut pas sleep pour rien
            time.sleep(0.1)  # 10Hz
        self.logger.log("[INFO] Statustext sent", wanna_print=False)

    def send_named_value_int(self, value: int, name = ""):
        """Envoie un NAMED_VALUE_INT.

        Args:
            value (int): Valeur.
            name (str): Nom.
        """
        if self.fin_mission:
            self.logger.log("[FAIL] Mission stopped: Impossible to send a NAMED_VALUE_INT")
            return False

        if len(name) > 10: # Limite
            name = name[:10]
            self.logger.log("[WARNING] Nom de NAMED_VALUE_INT trop long: tronqué")
        self.logger.log(f"[INFO] Sending named value int: {value}", wanna_print=False)
        self.master.mav.named_value_int_send(
            self.time_boot_ms, # time_boot_ms
            name.encode("ascii"), # name
            value # value
        )

    def send_cgm(self, cgm: CGM.CGM):
        """Envoie un CGM.

        Args:
            cgm (CGM.CGM): CGM.
        """
        self.send_named_value_int(value=cgm.value, name="CGM")

    def check_cgm(self, cgm: CGM.CGM) -> bool:
        """Vérifie si un cgm a été reçu.

        Args:
            cgm (CGM.CGM): CGM à attendre.

        Returns:
            bool: True si le cgm est là, False sinon.
        """
        return bool(cgm in self.cgm)

    def delete_cgm(self, cgm: CGM.CGM) -> None:
        """Supprime le CGM.

        Args:
            cgm (CGM.CGM): CGM.
        """
        if cgm in self.cgm:
            self.cgm.remove(cgm)

    # ------------------
    # Attente de données
    # ------------------

    def wait_motors_armed(self, source_system: int | None = None, timeout: float | None = 4) -> bool | None:
        """Attend l'armement des moteurs.

        Args:
            source_system (int | None): ID MAVLink source à attendre. Par défaut, vaut celui du master.
            timeout (float | None): Timeout d'attente d'armement. 0 si pas d'attente souhaitée (renvoie None). None si pas de timeout.

        Returns:
            bool | None: Moteurs armés ou non. None si fin de mission ou pas de donnée reçue (après timeout).
        """
        if timeout == 0:
            self.logger.log("[INFO] Timeout null: not waiting for armament")
            return None

        self.logger.log("[INFO] Waiting for armament..")
        start_time = time.time()
        while True:
            armed = self.motors_armed(source_system=source_system)
            if self.fin_mission:
                self.logger.log("[FAIL] Mission stopped: stop waiting for armament")
                return None

            if armed:
                self.logger.log("[SUCCESS] Drone armed: stop waiting for armament")
                return True

            if timeout is not None and time.time() > start_time + timeout:
                self.logger.log("[FAIL] Timeout: stop waiting for armament")
                return armed
            time.sleep(0.05)

    def wait_motors_disarmed(self, source_system: int | None = None, timeout: float | None = 4) -> bool | None:
        """Attend le désarmement des moteurs.

        Args:
            source_system (int | None): ID MAVLink source à attendre. Par défaut, vaut celui du master.
            timeout (float | None): Timeout d'attente de désarmement. 0 si pas d'attente souhaitée (renvoie None). None si pas de timeout.

        Returns:
            bool | None: Moteurs désarmés ou non. None si fin de mission ou pas de donnée reçue (après timeout).
        """
        if timeout == 0:
            self.logger.log("[INFO] Timeout null: not waiting for disarmament")
            return None

        self.logger.log("[INFO] Waiting for disarmament..")
        start_time = time.time()
        while True:
            disarmed = self.motors_disarmed(source_system=source_system)
            if self.fin_mission:
                self.logger.log("[FAIL] Mission stopped: stop waiting for disarmament")
                return None

            if disarmed:
                self.logger.log("[SUCCESS] Drone disarmed: stop waiting for disarmament")
                return True

            if timeout is not None and time.time() > start_time + timeout:
                self.logger.log("[FAIL] Timeout: stop waiting for disarmament")
                return disarmed
            time.sleep(0.05)

    def wait_mode_changed(self,
            mode: str | int | tuple[int, int, int],
            source_system: int | None = None,
            timeout: float | None = 4
        ) -> bool | None:
        """Attend le changement de mode.

        Args:
            mode (str | int | tuple[int, int, int]): Mode de vol. str: nom du mode. int: ID du mode sur ArduPilot. tuple[int, int, int]: (MAV_MODE_FLAG, Custom Main Mode, Custom Sub Mode) sur PX4.
            source_system (int | None): ID MAVLink source à attendre. Par défaut, vaut celui du master.
            timeout (float | None): Timeout d'attente de changement de mode. 0 si pas d'attente souhaitée (renvoie None). None si pas de timeout.

        Returns:
            bool | None: Mode changé ou non. None si fin de mission ou pas assez de données (après timeout).
        """
        if timeout == 0:
            self.logger.log("[INFO] Timeout null: not waiting for mode changing")
            return None

        # Recherche des IDs pour caractériser le mode de vol (si donné en str)
        if isinstance(mode, str):
            mode_mapping = self.mode_mapping(source_system=source_system)
            if mode_mapping is not None and mode in mode_mapping:
                key = mode_mapping[mode]
            else:
                self.logger.log(f"[FAIL] Trying to wait for mode changing. Unknow mode {mode}")
                self.logger.log(f"[LOG] mode_mapping({source_system}): {mode_mapping}", wanna_print=False)
                return False
        else:
            key = mode

        # Décomposition des IDs
        if isinstance(key, int):
            base_mode = mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED
            custom_main_mode = key
            custom_sub_mode = 0
        elif isinstance(key, tuple):
            if len(key) != 3:
                self.logger.log(f"[FAIL] Trying to wait for mode changing. Invalid mode: {key}")
                return False
            for i in key:
                if not isinstance(i, int):
                    self.logger.log(f"[FAIL] Trying to wait for mode changing. Invalid mode: {key}")
                    return False
            base_mode = key[0]
            custom_main_mode = key[1]
            custom_sub_mode = key[2]
        else:
            self.logger.log(f"[FAIL] Trying to wait for mode changing. Invalid mode: {key}")
            return False

        self.logger.log("[INFO] Waiting for mode change..")
        # Attente du changement de mode
        start_time = time.time()
        while True:
            if self.fin_mission:
                self.logger.log("[FAIL] Mission stopped: stop waiting for mode changing")
                return None

            if self.autopilot_int(source_system=source_system) == mavutil.mavlink.MAV_AUTOPILOT_PX4:
                if self.base_mode(source_system=source_system) == base_mode and \
                self.custom_main_mode(source_system=source_system) == custom_main_mode and \
                self.custom_sub_mode(source_system=source_system) == custom_sub_mode:
                    self.logger.log("[SUCCESS] Mode changed: stop waiting for mode changing")
                    return True
            else:
                if self.custom_mode(source_system=source_system) == custom_main_mode:
                    self.logger.log("[SUCCESS] Mode changed: stop waiting for mode changing")
                    return True

            if time.time() > start_time + timeout:
                self.logger.log("[FAIL] Timeout: stop waiting for mode changing")
                if isnan(self.base_mode(source_system=source_system)) or isnan(self.custom_mode(source_system=source_system)):
                    return None
                return False
            time.sleep(0.05)

    def wait_gps_fix(self, source_system: int | None = None, timeout: float | None = None) -> bool | None:
        """Attend le GPS 3D fix.

        Args:
            source_system (int | None): ID MAVLink source à attendre. Par défaut, vaut celui du master.
            timeout (float | None): Timeout d'attente de GPS fix. 0 si pas d'attente souhaitée (renvoie None). None si pas de timeout.

        Returns:
            bool | None: GPS 3D fix ou non. None si fin de mission ou pas de donnée reçue (après timeout).
        """
        if timeout == 0:
            self.logger.log("[INFO] Timeout null: not waiting for gps fix")
            return None

        self.logger.log("[INFO] Waiting for gps fix..")
        start_time = time.time()
        while True:
            gps_fixed = self.gps_fix(source_system=source_system)
            if self.fin_mission:
                self.logger.log("[FAIL] Mission stopped: stop waiting for gps fix")
                return None

            if gps_fixed:
                self.logger.log("[SUCCESS] GPS 3D fix: stop waiting for gps fix")
                return True

            if timeout is not None and time.time() > start_time + timeout:
                self.logger.log("[FAIL] Timeout: stop waiting for gps fix")
                return gps_fixed
            time.sleep(0.05)

    def wait_proximity(self,
            lat: float,
            lon: float,
            relative_alt: float | None = None,
            alt: float | None = None,
            radius_acceptance: float = 1,
            timeout: float | None = None
        ) -> bool | None:
        """Attend d'atteindre une certaine distance entre le contrôleur de vol et un point GPS.

        Args:
            lat (float): Latitude du point GPS (en degrés).
            lon (float): Longitude du point GPS (en degrés).
            relative_alt (float | None): Altitude relative du point GPS (en mètres).
            alt (float | None): Altitude absolue (MSL) du point GPS (en mètres).
            radius_acceptance (float): Distance à atteindre.
            timeout (float | None): Timeout d'attente de proximité. 0 si pas d'attente souhaitée (renvoie None). None si pas de timeout.

        Returns:
            bool | None: Résultat de l'opération. None si fin de mission ou pas de donnée reçue (après timeout).
        """
        if timeout == 0:
            self.logger.log("[INFO] Timeout null: not waiting for proximity")
            return None

        self.logger.log("[INFO] Waiting for proximity..")
        start_time = time.time()
        while True:
            distance_prox = self.get_distance_with(
                lat=lat,
                lon=lon,
                relative_alt=relative_alt,
                alt=alt
            )
            if self.fin_mission:
                self.logger.log("[FAIL] Mission stopped: stop waiting for proximity")
                return None

            if distance_prox <= radius_acceptance:
                self.logger.log("[SUCCESS] Proximity reached: stop waiting for proximity")
                return True

            if timeout is not None and time.time() > start_time + timeout:
                self.logger.log("[FAIL] Timeout: stop waiting for proximity")
                if isnan(distance_prox):
                    return None
                return False
            time.sleep(0.05)

    def wait_for_home(self, source_system: int | None = None, timeout: float | None = None) -> tuple[float, float, float]:
        """Attend de recevoir la position HOME.

        Args:
            source_system (int | None): ID MAVLink source à attendre. Par défaut, vaut celui du master.
            timeout (float | None): Timeout d'attente de réception. 0 si pas d'attente souhaitée (renvoie NaN, NaN, NaN). None si pas de timeout.

        Returns:
            tuple:
                - **latitude_home** (*float*) – Latitude HOME (deg). NaN si fin de mission ou pas de donnée reçue (après timeout).
                - **longitude_home** (*float*) – Longitude HOME (deg). NaN si fin de mission ou pas de donnée reçue (après timeout).
                - **altitude_home** (*float*) – Altitude HOME (MSL, m). NaN si fin de mission ou pas de donnée reçue (après timeout).
        """
        start_time = time.time() - 0.01 # Petite tolérance de 10 ms

        if timeout == 0: # Résultat non souhaité
            self.logger.log("[INFO] Timeout null: not waiting for HOME")
            return float('NaN'), float('NaN'), float('NaN') # We don't care waiting for HOME position

        self.logger.log("[INFO] Waiting for HOME..")
        while True:
            if self.fin_mission:
                self.logger.log("[FAIL] Mission stopped: stop waiting for HOME")
                return float('NaN'), float('NaN'), float('NaN')

            m = self.get_msg(msg_type="HOME_POSITION", source_system=source_system)
            if m and m._timestamp >= start_time: # Si on l'a reçu après avoir commencé la recherche
                self.logger.log("[SUCCESS] HOME received: stop waiting for HOME")
                return m.latitude / 1e7, m.longitude / 1e7, m.altitude / 1e3

            if timeout is not None and time.time() > start_time + timeout:
                self.logger.log("[FAIL] Timeout: stop waiting for HOME")
                return float('NaN'), float('NaN'), float('NaN')

            time.sleep(0.05)

    def wait_command_ack(self,
            command: int,
            source_system: int | None = None,
            timeout: float | None = 2
        ) -> bool | None:
        """Attend de recevoir un COMMAND_ACK spécifique, et regarde s'il est accepté ou non.

        Args:
            command (int): MAV_CMD | Commande.
            source_system (int | None): ID MAVLink source du COMMAND_ACK. Par défaut, vaut celui du master.
            timeout (float | None): Timeout d'attente de réception du COMMAND_ACK. 0 si pas d'attente souhaitée (renvoie None). None si pas de timeout.

        Returns:
            bool | None: True si on a reçu un COMMAND_ACK accepté, False sinon. None si fin de mission ou timeout.
        """
        start_time = time.time() - 0.01 # Petite tolérance de 10 ms

        if timeout == 0: # Résultat non souhaité
            self.logger.log("[INFO] Timeout null: not waiting for COMMAND_ACK", wanna_print=False)
            return None

        self.logger.log("[INFO] Waiting for COMMAND_ACK..", wanna_print=False)
        while True:
            if self.fin_mission:
                self.logger.log("[FAIL] Mission stopped: stop waiting for COMMAND_ACK", wanna_print=False)
                return None

            m = self.get_msg(
                msg_type="COMMAND_ACK",
                source_system=source_system
            )
            if m and m.command == command and \
            getattr(m, "target_system", self.master.source_system) == self.master.source_system and \
            getattr(m, "target_component", self.master.source_component) == self.master.source_component:
                if m._timestamp >= start_time: # Si on l'a reçu après avoir commencé la recherche
                    # C'est le command_ack qui nous intéresse
                    self.logger.log("[SUCCESS] COMMAND_ACK received: stop waiting for COMMAND_ACK", wanna_print=False)
                    return bool(m.result == mavutil.mavlink.MAV_RESULT_ACCEPTED)

            if timeout is not None and time.time() > start_time + timeout:
                self.logger.log("[FAIL] Timeout: stop waiting for COMMAND_ACK", wanna_print=False)
                return None

            time.sleep(0.05)

    def wait_mission_ack(self,
            mission_type: int | None = None,
            source_system: int | None = None,
            timeout: float | None = 2
        ) -> bool | None:
        """Attend de recevoir un MISSION_ACK spécifique, et regarde s'il est accepté ou non.

        Args:
            mission_type (int): MAV_MISSION_TYPE | Nom de la mission.
            source_system (int | None): ID MAVLink source du MISSION_ACK. Par défaut, vaut celui du master.
            timeout (float | None): Timeout d'attente de réception du MISSION_ACK. 0 si pas d'attente souhaitée (renvoie None). None si pas de timeout.

        Returns:
            bool | None: True si on a reçu un MISSION_ACK accepté, False sinon. None si fin de mission ou timeout.
        """
        start_time = time.time() - 0.01 # Petite tolérance de 10 ms

        if timeout == 0: # Résultat non souhaité
            self.logger.log("[INFO] Timeout null: not waiting for MISSION_ACK", wanna_print=False)
            return None

        self.logger.log("[INFO] Waiting for MISSION_ACK..", wanna_print=False)
        while True:
            if self.fin_mission:
                self.logger.log("[FAIL] Mission stopped: stop waiting for MISSION_ACK", wanna_print=False)
                return None

            m = self.get_msg(
                msg_type="MISSION_ACK",
                source_system=source_system
            )
            if m and (mission_type is None or getattr(m, "mission_type", mission_type) == mission_type) and \
            m.target_system == self.master.source_system and \
            m.target_component == self.master.source_component:
                if m._timestamp >= start_time: # Si on l'a reçu après avoir commencé la recherche
                    # C'est le mission_ack qui nous intéresse
                    self.logger.log("[SUCCESS] MISSION_ACK received: stop waiting for MISSION_ACK", wanna_print=False)
                    return bool(m.type == mavutil.mavlink.MAV_MISSION_ACCEPTED)

            if timeout is not None and time.time() > start_time + timeout:
                self.logger.log("[FAIL] Timeout: stop waiting for MISSION_ACK", wanna_print=False)
                return None

            time.sleep(0.05)

    # -----------
    # Utilitaires
    # -----------
    
    def get_msg(self,
            msg_type: str,
            source_system: int | None = None
        ) -> any:
        """Renvoie le dernier message d'un certain type reçu d'un certain source_system.

        Args:
            msg_type (str): Type de message.
            source_system (int | None): ID MAVLink source du message. Par défaut, vaut celui du master.

        Returns:
            msg | None: Message MAVLink concerné ou None.
        """
        if source_system is None:
            source_system = self.master.target_system
        if source_system not in self.master.sysid_state:
            return None
        if msg_type not in self.master.sysid_state[source_system].messages:
            return None
        return self.master.sysid_state[source_system].messages.get(msg_type)

    def mode_mapping(self, source_system: int | None = None) -> dict:
        """Renvoie un dictionnaire associant les noms de modes à leurs ids, ou None si inconnu.

        Args:
            source_system (int | None): ID MAVLink de l'appareil. Par défaut, vaut celui du master.

        Returns:
            dict: Dictionnaire associant les noms de modes à leurs ids, ou None si inconnu.
        """
        # En gros c'est la fonction de base mais qui s'adapte aux autres sysid (et qui marche pour le multivéhicule)
        # Ca renvoie un dict qui associe chaque nom en str à un id en int (pour ArduPilot) ou tuple[int, int, int] (pour PX4)
        hb = self.get_msg(msg_type="HEARTBEAT", source_system=source_system)
        if hb is None:
            return None

        mav_type = hb.type
        mav_autopilot = hb.autopilot
        if mav_autopilot == mavutil.mavlink.MAV_AUTOPILOT_PX4:
            return mavutil.px4_map
        if mav_type is None:
            return None
        return mavutil.mode_mapping_byname(mav_type)

    def cartesian_to_geographic_point(self,
            north_displacement: float,
            east_displacement: float
        ) -> tuple[float, float]:
        """Donne les coordonnées GPS d'un point à partir d'une définition cartésienne (le drone étant l'origine).

        Args:
            north_displacement (float): Déplacement vers le Nord (m).
            east_displacement (float): Déplacement vers l'Est (m).

        Returns:
            tuple:
                - **latitude** (*float*) – Latitude (deg).
                - **longitude** (*float*) – Longitude (deg).

        Notes:
            lat (float): Latitude du point GPS (deg). NaN si aucune donnée GPS n'a été reçue.
            lon (float): Longitude du point GPS (deg). NaN si aucune donnée GPS n'a été reçue.
        """
        lat, lon, _, _ = self.position()
        if isnan(lat) and isnan(lon):
            return float('NaN'), float('NaN')
        start_point = Point(lat, lon)
        distance_meters = sqrt(north_displacement**2 + east_displacement**2)
        bearing = degrees(atan2(east_displacement, north_displacement))
        new_point = distance(meters=distance_meters).destination(start_point, bearing)
        return new_point.latitude, new_point.longitude

    # ---------
    # Connexion
    # ---------

    def open(self, timeout_heartbeat: float | None = None) -> None:
        """Ouvre la connexion. Faire bien attention à l'avoir fermée au préalable.

        Args:
            timeout_heartbeat (float | None): Temps d'attente des premiers heartbeats.
        """
        address = self._data_init["address"]
        target_system = self._data_init["target_system"]
        source_system = self._data_init["source_system"]
        source_component = self._data_init["source_component"]
        baud = self._data_init["baud"]
        pos_rate = self._data_init["pos_rate"]
        dialect = self._data_init["dialect"]

        self.logger.log("[INFO] Creating master object..", wanna_print=False)
        # Contrôleur de vol
        self.master: mavutil.mavfile = mavutil.mavlink_connection(
            device=address,
            baud=baud,
            source_system=source_system,
            source_component=source_component,
            autoreconnect=True
        )
        self.logger.log("[INFO] Master object created", wanna_print=False)
        try:
            self.timesync_handler.master = self.master
            self.mavthread.master = self.master

            if timeout_heartbeat != 0:
                # Callbacks appelés à chaque réception et envoi de messages
                self.master.mav.set_callback(self._recv_match_callback)
                if target_system is not None:
                    self.logger.log(f"[INFO] Waiting for HEARTBEAT from ({target_system}:{mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1})..") # (sysid:compid)
                else:
                    self.logger.log("[INFO] Waiting for HEARTBEAT..")
                start_time = time.time()
                while True:
                    if timeout_heartbeat is not None:
                        timeout_lst = start_time + timeout_heartbeat - time.time()
                        if timeout_lst <= 0:
                            raise TimeoutError("[FAIL] No HEARTBEAT received")
                    else:
                        timeout_lst = None

                    hb = self.master.recv_match(type="HEARTBEAT", blocking=True, timeout=timeout_lst)
                    if not hb:
                        raise TimeoutError("[FAIL] No HEARTBEAT received")

                    self.logger.log(f"[INFO] HEARTBEAT received from ({hb.get_srcSystem()}:{hb.get_srcComponent()})")
                    if (target_system is None or hb.get_srcSystem() == target_system) and hb.get_srcComponent() == mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1:
                        self.master.target_system = hb.get_srcSystem()
                        self.master.target_component = mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1
                        self.logger.log("[SUCCESS] Stop waiting for HEARTBEAT")
                        break
            else:
                self.logger.log("[INFO] No timeout for HEARTBEAT specified")
                ### Attributs modifiés à la main. Permet de ne pas appeler master.auto_mavlink_version, qui reset le send_callback à la réception du 1er message
                # Note : lorsque ce problème de callback sera enfin réglé, remplacer tout ça par : mavutil.set_dialect(dialect=dialect)
                self.master.first_byte = False # Comme si on avait déjà reçu un message
                self.master.WIRE_PROTOCOL_VERSION = "2.0" # On active MAVLink 2
                os.environ['MAVLINK20'] = '1' # On active MAVLink 2
                mavutil.set_dialect(dialect=dialect) # On charge le dialecte
                # Reste de la fonction master.auto_mavlink_version
                self.master.mav = mavutil.mavlink.MAVLink(self.master, srcSystem=self.master.source_system, srcComponent=self.master.source_component)
                self.master.mav.robust_parsing = self.master.robust_parsing
                self.master.WIRE_PROTOCOL_VERSION = mavutil.mavlink.WIRE_PROTOCOL_VERSION
                self.master.mav.set_callback(self._recv_match_callback)
                ### FIN
                self.master.target_system = 1 if target_system is None else target_system
                self.master.target_component = mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1

            self.master.mav.set_send_callback(self._send_callback)
            # Pour les versions de pymavlink <= 2.4.43, il faut set_send_callback après avoir reçu le premier message
            # Car le 1er message appel une fonction auto_mavlink_version, qui reset ce callback
            # J'ai fait une pull request qui règlera ce problème dans les versions futures

            self.timesync_handler.master = self.master
            self.mavthread.master = self.master
            self.mavthread.start_threads()

            if timeout_heartbeat != 0:
                self.set_msg_rate(
                    msg_type="GLOBAL_POSITION_INT",
                    rate=pos_rate,
                    timeout_ack=2
                )
                self.set_msg_rate(
                    msg_type="ATTITUDE",
                    rate=pos_rate,
                    timeout_ack=2
                )
                self.set_msg_rate(
                    msg_type="EXTENDED_SYS_STATE",
                    rate=2,
                    timeout_ack=2
                )

            self.logger.log("[SUCCESS] Connection initialized")
        except Exception as e: #Permet la fermeture de la connexion en cas d'erreur
            try:
                self.master.close()
            except Exception:
                pass
            raise e

    def close(self) -> None:
        """Closes the connection with the flight controller.
        """
        self.logger.log("[INFO] Closing..")
        self.mavthread.stop_threads()
        try:
            self.master.close()
        except Exception:
            self.logger.log(exception=True)
        self.logger.log("[SUCCESS] Closed")

    # -------------------------------------------------------------------------------
    # Callbacks (à modifier selon vos envies, soit ici, soit dans des classes filles)
    # -------------------------------------------------------------------------------

    def _fs_long(self):
        """Fonction à effectuer en cas de FS_LONG (utile par ex pour respecter le crash de l'avion après la perte de connexion si vous avez pas de script LUA).
        À réécrire, soit dans cette classe, soit dans les classes filles.
        """
        # Vérifiez le message envoyé par le contrôleur de vol en cas de FS_LONG ! Modifiez le callback de réception
        if False:
            # Je vous met ce qu'on a utilisé de notre côté. Faites attention, ça tue l'avion (je me répète mais c'est important)
            self.disarm(force=True)
            self.change_mode("MANUAL")
            self.master.source_system = 255 # Doit être égal au paramètre SYSID_MYGCS.
            # Changement de SYSID_MYGCS déconseillé. Si SYSID_MYGCS ne vaut pas 255, vous perdez l'accès à la télécommande (si vous êtes en ELRS MAVLink)
            while True:
                self.master.mav.rc_channels_override_send(
                    self.master.target_system,
                    self.master.target_component,
                    0, 2000, 0, 0, 2000, 0, 2000, 0 # (à changer en fonction de vos servos)
                )
                self.change_mode("MANUAL") # Il faut spammer ça sinon parfois il passe en RTL
                time.sleep(0.2)

    def _recv_match_callback(self, m):
        """Fonction appelée à chaque réception de message.
        Possibilité de réécrire, soit dans cette classe, soit dans les classes filles.
        """
        try:
            # Analyse
            if m.get_type() == "COMMAND_ACK" and getattr(m, "target_system", self.master.source_system) == self.master.source_system and getattr(m, "target_component", self.master.source_component) == self.master.source_component:
                # On vérifie que le COMMAND_ACK nous est destiné
                command = mavutil.mavlink.enums["MAV_CMD"][m.command].name[8:]
                result = mavutil.mavlink.enums["MAV_RESULT"][m.result].name[11:]
                self.logger.log(f"Got COMMAND_ACK: {command}: {result}")
            elif m.get_type() == "MISSION_ACK" and m.target_system == self.master.source_system and m.target_component == self.master.source_component:
                # On vérifie que le MISSION_ACK nous est destiné
                t = mavutil.mavlink.enums["MAV_MISSION_TYPE"][m.mission_type].name[12:]
                res = mavutil.mavlink.enums["MAV_MISSION_RESULT"][m.type].name[12:]
                self.logger.log(f"Got MISSION_ACK: {t}: {res}")
            elif m.get_type() == "STATUSTEXT":
                result = self.statustext_receiver._add(m)
                if result is not None: # We have completed a STATUSTEXT
                    self.logger.log(f"AP: {result.text}")
                    if result.text.startswith("RC Long Failsafe On:"): # Long FS, vérifiez le message dans votre cas !!
                        self._fs_long()
            elif m.get_type() == "NAMED_VALUE_INT":
                if m.name == "CGM": # C'est un CGM
                    cgm = CGM.CGM.get(value=m.value)
                    self.logger.log(cgm.short_description_str)
                    self.cgm.add(cgm)
                    if self._cgm_hook and cgm.value != 0:
                        try:
                            self._cgm_hook(cgm)
                        except Exception:
                            pass
            elif m.get_type() == "TIMESYNC":
                self.timesync_handler._receive(m)
        except Exception:
            self.logger.log(exception=True)

    def _send_callback(self, m):
        """Fonction appelée à chaque envoi de messages
        Possibilité de réécrire, soit dans cette classe, soit dans les classes filles.
        """
        try:
            if m.get_type() == "NAMED_VALUE_INT":
                if m.name == "CGM": # CGM
                    cgm = CGM.CGM.get(value=m.value)
                    self.logger.log(cgm.short_description_str)
                    self.cgm.add(cgm)
            elif m.get_type() == "TIMESYNC":
                self.timesync_handler._send_callback(m)
            elif m.get_type() == "HEARTBEAT":
                self.timesync_handler._send_heartbeat_callback()
                if self._send_automatic_home_request:
                    if self._nb_heartbeat_since_last_home_request >= self._home_request_delay:
                        if self._sysid_to_request_home is None or isinstance(self._sysid_to_request_home, int):
                            if self._sysid_to_request_home is None:
                                sysid = self.master.target_system
                            else:
                                sysid = self._sysid_to_request_home
                            self.master.mav.command_long_send(
                                sysid, # target_system
                                mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1, # target_component
                                mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE, # Commande pour demander un message
                                0, # confirmation
                                242, # param1 (Message ID)
                                0,0,0,0,0,0 # param2-7 (unused)
                            )
                        else: # list[str]
                            for sysid in self._sysid_to_request_home:
                                self.master.mav.command_long_send(
                                    sysid, # target_system
                                    mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1, # target_component
                                    mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE, # Commande pour demander un message
                                    0, # confirmation
                                    242, # param1 (Message ID)
                                    0,0,0,0,0,0 # param2-7 (unused)
                                )
                        self._nb_heartbeat_since_last_home_request = 1
                    else:
                        self._nb_heartbeat_since_last_home_request += 1
            elif m.get_type() == "COMMAND_LONG":
                enum = mavutil.mavlink.enums["MAV_CMD"][m.command]
                str_to_log = f"""[LOG] Sending COMMAND_LONG
                target_system: {m.target_system}
                target_component: {m.target_component}
                command: {enum.name} ({m.command})
                param1: {m.param1} ({enum.param[1]})
                param2: {m.param2} ({enum.param[2]})
                param3: {m.param3} ({enum.param[3]})
                param4: {m.param4} ({enum.param[4]})
                param5: {m.param5} ({enum.param[5]})
                param6: {m.param6} ({enum.param[6]})
                param7: {m.param7} ({enum.param[7]})
                """
                self.logger.log(str_to_log, wanna_print=False)
            elif m.get_type() == "MISSION_ITEM_INT":
                str_to_log = f"""[LOG] Sending MISSION_ITEM_INT
                target_system: {m.target_system}
                seq: {m.seq}
                frame: {mavutil.mavlink.enums["MAV_FRAME"][m.frame].name} ({m.frame})
                command: {mavutil.mavlink.enums["MAV_CMD"][m.command].name} ({m.command})
                param1: {m.param1} ({mavutil.mavlink.enums["MAV_CMD"][m.command].param[1]})
                param2: {m.param2} ({mavutil.mavlink.enums["MAV_CMD"][m.command].param[2]})
                param3: {m.param3} ({mavutil.mavlink.enums["MAV_CMD"][m.command].param[3]})
                param4: {m.param4} ({mavutil.mavlink.enums["MAV_CMD"][m.command].param[4]})
                x: {m.x}
                y: {m.y}
                z: {m.z}
                mission_type: {mavutil.mavlink.enums["MAV_MISSION_TYPE"][m.mission_type].name} ({m.mission_type})
                """
                self.logger.log(str_to_log, wanna_print=False)
        except Exception:
            self.logger.log(exception=True)
