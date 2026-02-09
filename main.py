from pymavlink_code.class_MAVLinCS import MAVLinCS
from Camera.class_Camera import Camera
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
        logger: Logger = Logger()):
        super().__init__(address, source_system, source_component, target_system, baud, timeout_heartbeat, send_automatic_timesync, timesync_delay, send_automatic_home_request, home_request_delay, sysid_to_request_home, pos_rate, dialect, logger)
        
    def precision_land(self):
        ...
        
    def loiter(self, gz_camera):
        while True:
            result = gz_camera.analyse(affichage=True)
            if result[-2] is not None:
                print('[Aruco] Going to AruCo marker')
                print(result[0], result[1], result[2])
                self.send_landing_target(result[0], result[1], result[2])
                
            time.sleep(0.01)


try:
    drone = Drone(
        address="/dev/ttyAMA0",
        source_system=201,
        source_component=mavutil.mavlink.MAV_COMP_ID_MISSIONPLANNER,
        target_system=1,
        baud=57600,
        timeout_heartbeat=None,
    )


    # Gazebo Camera
    gz_camera = Camera()

    # Armement des deux drones
    armed_drone = False
    while not armed_drone:
        armed_drone = drone.arm()
        time.sleep(5)

    if armed_drone:
        # Takeoff simple
        drone.logger.log("Drone armé")
        drone.takeoff(3)
        time.sleep(5)
        drone.return_to_launch()

        
except Exception as e:
    print("Erreur innatendue")
    print(e)

finally:
    try:
        drone.close()
        gz_camera.close()
    except Exception:
        pass
    print("Connexion fermée")

