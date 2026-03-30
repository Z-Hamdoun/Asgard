import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from pymavlink_code.class_MAVLinCS import MAVLinCS
from Camera.class_Camera import Camera
from pymavlink import mavutil
from divers.class_Logger import Logger
from pnp.algo import PnPLandingSystem
from class_Drone import Drone


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
        
        # Le petit drone doit suivre le gros drone
        drone1.do_follow_with_takeoff()

        
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

