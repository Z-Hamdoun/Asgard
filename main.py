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
            result = gz_camera.analyse()
            gz_camera.get_frame(save=True)
            if result[-2] is not None:
                gz_camera.logger.log("OUI ARUCO")
                print('[Aruco] Going to AruCo marker')
                print(result[0], result[1], result[2])
                self.send_landing_target(result[0], result[1], result[2])
                
            time.sleep(0.01)


try:
    drone = Drone(
        address="/dev/ttyAMA0",
        source_component=mavutil.mavlink.MAV_COMP_ID_ONBOARD_COMPUTER,
        target_system=1,
        baud=921600,
    )


    # camera = Camera(simulation=None, logger=Logger("log.txt"))

    while True:
        inpt = input(">> ")
        if inpt == "guided":
            success = drone.change_mode("GUIDED")
            print(success)
        
        if inpt == "stab":
            success = drone.change_mode("STABILIZE")
        
        elif inpt == "arm":
            drone.master.mav.command_long_send(
            drone.master.target_system, # target_system
            mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1, # target_component
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, # command
            1, # confirmation
            1, # param1 (Arm)
            0, # param2 (Force)
            0,0,0,0,0 # param3-7 (unused)
        )


        
        elif inpt == "takeoff":
            alt = float(input("Altitude: "))
            success = drone.takeoff(altitude=alt)
            print(success)

        elif inpt == "hold":
            success = drone.change_mode("FLOWHOLD")
            print(success)
        
        elif inpt == "land":
            success = drone.change_mode("LAND")
            print(success)
        
        else:
            print("Bad command")
        
except Exception as e:
    print("Erreur innatendue")
    print(e)

finally:
    try:
        drone.close()
    except Exception:
        pass
    print("Connexion fermée")

