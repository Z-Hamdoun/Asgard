from pymavlink_code.class_MAVLinCS import MAVLinCS
from Camera.class_Camera import Camera
from pymavlink import mavutil
import time

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
        # simple takeoff
        drone0.logger.log("Drone armé")
        drone0.takeoff(3)
        drone1.takeoff(3)

        # Exemple de code pour recuperer les images de la camera gazebo
        # while True:
        #    gz_camera.get_frame(affiche=True)
        #    time.sleep(0.01)
except Exception:
    print("Erreur innatendue")

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

