from pymavlink_code.class_MAVLinCS import MAVLinCS
from pymavlink import mavutil
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
        logger = None,
        camera_topic="/world/iris_runway/model/iris_with_gimbal/model/gimbal/link/pitch_link/sensor/camera/image"):
        
        super().__init__(address, source_system, source_component, target_system, baud, timeout_heartbeat, send_automatic_timesync, timesync_delay, send_automatic_home_request, home_request_delay, sysid_to_request_home, pos_rate, dialect, logger, camera_topic)
    
        
#    def loiter_pnp(self):
#        while True:
#            frame = self.camera.get_frame(affiche=True)
#            vector = pnp.get_landing_vector(frame, verbose=True)
#            if vector:
#                print("PNP DETECTE!!!!!!!!!!")
#                self.send_landing_target(-vector[0], vector[1], vector[2])
#            time.sleep(0.01)
    
#    def loiter(self):
#        while True:
#            result = self.camera.analyse(affichage=False)
#            if result[-2] is not None:
#                print('[Aruco] Going to AruCo marker')
#                print(result[0], result[1], result[2])
#                self.send_landing_target(result[0], result[1], result[2])
#            time.sleep(0.05)
    