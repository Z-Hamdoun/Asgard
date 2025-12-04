from pymavlink_code.class_MAVLinCS import MAVLinCS
from Camera.class_Camera import Camera
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
        logger = ...):
        super().__init__(address, source_system, source_component, target_system, baud, timeout_heartbeat, send_automatic_timesync, timesync_delay, send_automatic_home_request, home_request_delay, sysid_to_request_home, pos_rate, dialect, logger)
        
    def precision_land(self):
        ...
        
    def loiter(self):
        ...


try:
    # Master drone
    drone0 = MAVLinCS(
        address="127.0.0.1:14550",
        source_system=201,
        source_component=mavutil.mavlink.MAV_COMP_ID_MISSIONPLANNER,
        target_system=1,
        baud=57600,
        timeout_heartbeat=None,
    )

    # Petit drone
    drone1 = MAVLinCS(
        address="127.0.0.1:14560",
        source_system=201,
        source_component=mavutil.mavlink.MAV_COMP_ID_MISSIONPLANNER,
        target_system=2,
        baud=57600,
        timeout_heartbeat=None,
    )

    # Gazebo Camera
    gz_camera = Camera(simulation='SITL')

    # Armement des deux drones
    armed_drone0 = drone0.arm()
    armed_drone1 = drone1.arm()

    if armed_drone0 and armed_drone1:
        # Takeoff simple
        drone0.logger.log("Drone armé")
        drone0.takeoff(3)
        drone1.takeoff(3)

        # Exemple de code pour recuperer les images de la camera gazebo
        while True:
            result = gz_camera.analyse(affichage=True)
            if result[-2] is not None:
                print('[Aruco] Going to AruCo marker')
                print(result[0], result[1], result[2])
                drone0.send_landing_target(result[0], result[1], result[2])
                
            time.sleep(0.01)
except Exception as e:
    print("Erreur innatendue")
    print(e)

# interruption manuelle avec Ctrl+C
except KeyboardInterrupt:
    print("Arrêt demandé")

finally:
    try:
        drone0.close()
        drone1.close()
        gz_camera.close()
    except Exception:
        pass
    print("Connexion fermée")

