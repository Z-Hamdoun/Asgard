from class_Drone import Drone
from valhala.states import Idle as Valhalla_Idle
from Camera.class_Camera import Camera
from divers.class_Logger import Logger
from pymavlink import mavutil
import time


def main():
    
    # 1. Init Logger et Camera
    logger = Logger(log_file='logs.txt')
    gz_camera = Camera(simulation='SITL')

    # 2. Init Drones
    # Master
    drone0 = Drone(
        address="127.0.0.1:14550",
        source_system=201,
        target_system=1,
        logger=logger
    )
    
    # Slave
    drone1 = Drone(
        address="127.0.0.1:14560",
        source_system=201,
        target_system=2,
        logger=logger
    )

    # 3. Injection des dépendances
    # On donne la caméra au drone 0 pour qu'il l'utilise dans ses États
    drone0.camera = gz_camera 

    # 5. Lancement des machines à états
    drone0.current_state = Valhalla_Idle()
    # drone1.current_state = Valkyrie_Idle()

    if drone0.current_state: drone0.current_state.on_enter(drone0)
    # if drone1.current_state: drone1.current_state.on_enter(drone1)

    # Boucle Principale
    try:
        while True:
            drone0.update()
            # drone1.update()
            
            time.sleep(0.01) # 100 HZ

    except KeyboardInterrupt:
        print("Arrêt demandé")
    finally:
        drone0.close()
        drone1.close()
        gz_camera.close()
        print("Fermeture propre.")

if __name__ == "__main__":
    main()