from pymavlink_code.class_MAVLinCS import MAVLinCS
from camera.class_Camera import Camera
from pymavlink import mavutil
from utils.class_Logger import Logger
import time


class Drone(MAVLinCS):
    def __init__(self,
        address,
        source_system = 255, 
        source_component = mavutil.mavlink.MAV_COMP_ID_MISSIONPLANNER,
        target_system = None,
        baud = 57600,
        timeout_heartbeat = None,
        send_automatic_timesync = True,
        timesync_delay = 3,
        send_automatic_home_request = True,
        home_request_delay = 3,
        sysid_to_request_home = None,
        pos_rate = 4,
        dialect = "ardupilotmega",
        logger: Logger = Logger(log_file='logs.txt'),
        camera_topic="/world/iris_runway/model/iris_with_gimbal/model/gimbal/link/pitch_link/sensor/camera/image"):
        
        super().__init__(address, source_system, source_component, target_system, baud, timeout_heartbeat, send_automatic_timesync, timesync_delay, send_automatic_home_request, home_request_delay, sysid_to_request_home, pos_rate, dialect, logger)
        
        # Variables d'Etat
        self.current_state = None
        self.camera = Camera(simulation=None, camera_topic=camera_topic, logger=self.logger)
        self.target_system = target_system # On garde l'ID pour les logs, 1 pour drone maitre et 2 pour l'autre
    
    def precision_land(self):
        ...
        
    def loiter_pnp(self):
        while True:
            frame = self.camera.get_frame(affiche=True)
            vector = pnp.get_landing_vector(frame, verbose=True)
            if vector:
                print("PNP DETECTE!!!!!!!!!!")
                self.send_landing_target(-vector[0], vector[1], vector[2])
            time.sleep(0.01)
    
    def loiter(self):
        while True:
            result = self.camera.analyse(affichage=False)
            if result[-2] is not None:
                print('[Aruco] Going to AruCo marker')
                print(result[0], result[1], result[2])
                self.send_landing_target(result[0], result[1], result[2])
            time.sleep(0.05)
    
    
        
    def update(self):
        """Fait avancer la FSM d'un pas"""
        if self.current_state:
            # Logique de l'etat
            next_state = self.current_state.on_execute(self)
            
            # Transition
            if next_state != self.current_state:
                self.current_state.on_exit(self)
                log_msg = f"[FSM] Transition {self.current_state.name} --> {next_state.name}"

                if self.logger:
                    self.logger.log(log_msg)
                self.current_state = next_state
                self.current_state.on_enter(self)
