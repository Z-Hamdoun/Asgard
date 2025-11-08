import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from pymavlink import mavutil
import time

from divers.class_Local_Position_Sensor import Local_Position_Sensor
from pymavlink_code.class_MavThread import MavThread
from divers.class_Logger import Logger

# Paramètres d'origine à changer (mettre pas trop loin pour pas faire paniquer le compass)
LAT_ORIGINE = -31.9508512
LON_ORIGINE = 115.863278
ALT_ORIGINE = 10

class Local_Position_Handler:
    """Permet de donner la position locale au drone"""
    def __init__(self,
            address: str,
            simulation: bool,
            target_system: int,
            baud: int = 921600,
            pose_topic: str = "/world/iris_runway/dynamic_pose/info",
            drone_name_gz: str = "iris_with_gimbal",
            origin_set_delay: int = 4,
            logger: Logger = Logger()
        ):
        """Initialise le GPS.

        Args:
            address (str): Adresse de connexion au FC.
            simulation (bool). Si on est sur Gazebo ou non.
            target_system (int): ID MAVLink du drone et du GPS.
            baud (int): Baudrate de connexion.
            pose_topic (str): Topic Gazebo avec l'entièreté des positions.
            drone_name_gz (str): Nom du drone sur Gazebo.
            origin_set_delay (int): Délai entre 2 envoi de set HOME + set origin EKF.
            logger (Logger): Logger utilisé.
        """
        self.logger = logger
        self.origin_set_delay = origin_set_delay

        self.sensor = Local_Position_Sensor(
            simulation=simulation,
            pose_topic=pose_topic,
            drone_name_gz=drone_name_gz,
            logger=logger
        )

        self.logger.log("[INFO] Waiting for first position from sensor..")
        while not self.sensor.pos_initialized:
            time.sleep(0.1) # On attend d'avoir reçu au moins une position
        self.logger.log("[SUCCESS] First position received from sensor")

        self.master = mavutil.mavlink_connection(
            device=address,
            baud=baud,
            source_system=target_system,
            source_component=mavutil.mavlink.MAV_COMP_ID_GPS,
            autoreconnect=True
        )
        try:
            self.logger.log("[INFO] Waiting for HEARTBEAT..")
            while True:
                m = self.master.recv_match(
                    type="HEARTBEAT",
                    blocking=True
                )
                if m.get_srcSystem() == target_system and m.get_srcComponent() == mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1:
                    self.master.target_system = target_system
                    self.master.target_component = mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1
                    break
            self.logger.log("[SUCCESS] HEARTBEAT received")
            # Gestion des threads
            self.mavthread = MavThread(self.master, logger=logger)
            self.mavthread.start_heartbeat_thread()
            time.sleep(0.1)
            self.logger.log("[SUCCESS] Local Position Handler initialized")
        except Exception as e: #Permet la fermeture de la connexion en cas d'erreur
            try:
                self.mavthread.stop_heartbeat_thread()
            except Exception:
                pass
            try:
                self.master.close()
            except Exception:
                pass
            raise e

    @property
    def time_usec(self) -> int:
        """timestamp Unix en us"""
        return int(time.time() * 1e6)

    def set_home(self) -> None:
        """Set la position HOME du drone.
        """
        self.logger.log("[INFO] Setting HOME...", wanna_print=False)
        self.master.mav.command_int_send(
            self.master.target_system,
            mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1,
            mavutil.mavlink.MAV_FRAME_GLOBAL,
            mavutil.mavlink.MAV_CMD_DO_SET_HOME,
            0, 0, 0, 0, 0, 0,
            int(LAT_ORIGINE * 1e7), int(LON_ORIGINE * 1e7), ALT_ORIGINE
        )

    def set_ekf_origin(self) -> None:
        """Set l'origine EKF du drone.
        """
        self.logger.log("[INFO] Setting EKF origin...", wanna_print=False)
        self.master.mav.set_gps_global_origin_send(
            self.master.target_system,
            int(LAT_ORIGINE*1e7), int(LON_ORIGINE*1e7), int(ALT_ORIGINE*1e3), 0
        )

    def send_vision_position_estimate(self):
        """Envoi un VISION_POSITION_ESTIMATE
        """
        self.master.mav.vision_position_estimate_send(
            self.time_usec,
            self.sensor.x, self.sensor.y, self.sensor.z,
            0, 0, 0,
            [float('NaN')]*21, 0
        )

    def start(self):
        """Commence l'envoi des données de position (boucle).
        """
        self.logger.log("[INFO] Start sending VISION_POSITION_ESTIMATE")
        n = 10 * self.origin_set_delay
        while True:
            try:
                self.send_vision_position_estimate()
                n += 1

                # Origine
                if n >= 10 * self.origin_set_delay:
                    self.set_ekf_origin()
                    self.set_home()
                    n = 0
            except Exception:
                pass
            time.sleep(0.1)

    def close(self) -> None:
        """Closes the connection with the flight controller."""
        self.logger.log("[INFO] Closing..")
        self.mavthread.stop_heartbeat_thread()
        try:
            self.master.close()
        except Exception:
            self.logger.log(exception=True)
        self.logger.log("[SUCCESS] Closed")
