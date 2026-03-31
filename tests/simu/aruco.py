import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from class_Drone import Drone


try:
    drone = Drone(
        address="127.0.0.1:14550",
        target_system=1,
    )


    # Armement des deux drones
    armed_drone = drone.arm()

    if armed_drone:
        # Takeoff simple
        drone.logger.log("Drone armé")
        drone.takeoff(3)
        

        
except Exception as e:
    print("Erreur innatendue")
    print(e)

# interruption manuelle avec Ctrl+C
except KeyboardInterrupt:
    print("Arrêt demandé")

finally:
    try:
        drone.camera.close()
        drone.close()
        
    except Exception:
        pass
    print("Connexion fermée")

