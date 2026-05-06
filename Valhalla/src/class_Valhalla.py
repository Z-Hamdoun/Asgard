import sys
import os
import time
from pymavlink import mavutil
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from pymavlink_code.code_de_gestion_de_missions import CGM

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