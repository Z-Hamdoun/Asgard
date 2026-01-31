from pymavlink_code.class_MAVLinCS import MAVLinCS
from pymavlink import mavutil
from divers.class_Logger import Logger
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
        logger: Logger = Logger(log_file='logs.txt')):
        
        super().__init__(address, source_system, source_component, target_system, baud, timeout_heartbeat, send_automatic_timesync, timesync_delay, send_automatic_home_request, home_request_delay, sysid_to_request_home, pos_rate, dialect, logger)
        
        # Variables d'Etat
        self.current_state = None
        self.camera = None # Sera assigne dans le main
        self.target_system = target_system # On garde l'ID pour les logs, 1 pour drone maitre et 2 pour l'autre
        
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
