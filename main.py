import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from pymavlink_code.class_MAVLinCS import MAVLinCS
from Camera.class_Camera import Camera
from pymavlink import mavutil
from divers.class_Logger import Logger
from pnp.algo import PnPLandingSystem
import time
from threading import Thread


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
        logger: Logger = Logger(log_file="logs.txt",),
        camera_topic="/world/iris_runway/model/iris_with_gimbal/model/gimbal/link/pitch_link/sensor/camera/image"):
        super().__init__(address, source_system, source_component, target_system, baud, timeout_heartbeat, send_automatic_timesync, timesync_delay, send_automatic_home_request, home_request_delay, sysid_to_request_home, pos_rate, dialect, logger)
        self.camera = Camera(simulation='SITL', camera_topic=camera_topic, logger=self.logger)
        
    def precision_land(self):
        ...
        
    def loiter_pnp(self, gz_camera):
        while True:
            frame = gz_camera.get_frame(affiche=True)
            vector = pnp.get_landing_vector(frame, verbose=True)
            if vector:
                print("PNP DETECTE!!!!!!!!!!")
                self.send_landing_target(-vector[0], vector[1], vector[2])
            time.sleep(0.01)
    
    def loiter(self, gz_camera):
        while True:
            result = self.camera.analyse(affichage=False)
            if result[-2] is not None:
                print('[Aruco] Going to AruCo marker')
                print(result[0], result[1], result[2])
                self.send_landing_target(result[0], result[1], result[2])
            time.sleep(0.01)


def valhalla():
    armed = drone0.arm()
    if armed:
        # Takeoff simple
        drone0.logger.log("Drone armé")
        drone0.takeoff(3)
        
        # Loitering pour le Gros drone:
        drone0.loiter()

        

def valkyrie():
    armed = drone1.arm()
    if armed:
        drone1.takeoff(3)
        drone1.do_follow(1)


try:
    # Master drone
    drone0 = Drone(
        address="127.0.0.1:14550",
        target_system=1,
    )

    # Petit drone
    drone1 = Drone(
        address="127.0.0.1:14560",
        target_system=2,
        baud=57600,
        timeout_heartbeat=None,
    )

    # Gazebo Camera
    gz_camera = Camera(simulation='SITL', camera_topic="/world/iris_runway/model/drone1/model/gimbal/link/pitch_link/sensor/camera/image")
    
    # PNP
    pnp = PnPLandingSystem()

    # Armement des deux drones
    armed_drone0 = drone0.arm()
    armed_drone1 = drone1.arm()

    if armed_drone0 and armed_drone1:
        # Takeoff simple
        drone0.logger.log("Drone armé")
        drone0.takeoff(3)
        drone1.takeoff(5)
        
        # Loitering pour le Gros drone:
        drone1.loiter_pnp(gz_camera)

        
except Exception as e:
    print("Erreur innatendue")
    print(e)

# interruption manuelle avec Ctrl+C
except KeyboardInterrupt:
    print("Arrêt demandé")

finally:
    try:
        drone0.camera.close()
        drone0.close()
        drone1.close()
        
    except Exception:
        pass
    print("Connexion fermée")

