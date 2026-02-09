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
        logger: Logger = Logger(log_file="log_rpi.txt")):
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
    # drone = Drone(
    #     address="/dev/ttyAMA0",
    #     source_system=201,
    #     source_component=mavutil.mavlink.MAV_COMP_ID_MISSIONPLANNER,
    #     target_system=1,
    #     baud=57600,
    #     timeout_heartbeat=None,
    #     logger=Logger(log_file="logs_rpi.txt")
    # )


    # Gazebo Camera
    camera = Camera()

    # Armement des deux drones
    # armed_drone = False
    # while not armed_drone:
    #     armed_drone = drone.arm()
    #     time.sleep(5)

    # if armed_drone:
    #     # Takeoff simple
    #     drone.logger.log("Drone armé")
    #     drone.takeoff(3)
    #     time.sleep(5)
    #     drone.master.mav.set_position_target_local_ned_send(
    #     0,                          # time_boot_ms
    #     drone.master.target_system, # target_system
    #     drone.master.target_component,
    #     mavutil.mavlink.MAV_FRAME_BODY_OFFSET_NED, # Repère par rapport au drone
    #     0b110111111000,             # Masque (On veut juste la POSITION, on ignore le reste)
    #     3, 0, 0,                    # X=3m (Devant), Y=0, Z=0
    #     0, 0, 0,                    # Vitesses (ignorées)
    #     0, 0, 0,                    # Accel (ignorées)
    #     0, 0                        # Yaw (ignoré)
    # )
    #     time.sleep(5)
    #     camera.get_frame(save=True)
    #     fin = drone.return_to_launch()
    #     if fin:
    #         drone.close()
    camera.get_frame(save=True)
    camera.close()
        
except Exception as e:
    print("Erreur innatendue")
    print(e)

finally:
    try:
        # drone.close()
        camera.close()
    except Exception:
        pass
    print("Connexion fermée")

