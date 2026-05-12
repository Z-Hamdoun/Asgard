import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from class_Drone import Drone
from threading import Thread
import time


def send_rc(drone):
    while True:
        drone.master.mav.rc_channels_override_send(
                drone.master.target_system,
                drone.master.target_component,
                0, 0, 1500, 0,
                0, 0, 0, 1900
            )
        time.sleep(0.01)
    
try:
    drone = Drone(
        address="127.0.0.1:14550",
        target_system=1,
        
    )

    armed_drone = drone.arm()

    if armed_drone:
        drone.logger.log("Drone armé")
        took_off = False
        while not took_off:
            took_off = drone.takeoff(3)
            time.sleep(5)
        
        # Definition des threads
        analyse_image = Thread(target=drone.loiter)
        rc_thread = Thread(target=send_rc, args=(drone, ))
        
        time.sleep(10)
        rc_thread.start()
        analyse_image.start()
        drone.change_mode("LOITER")
        rc_thread.join()
        analyse_image.join()
        

        
except Exception as e:
    print("Erreur innatendue")
    print(e)

except KeyboardInterrupt:
    print("Arrêt demandé")

finally:
    try:
        drone.camera.close()
        drone.close()
        
    except Exception:
        pass
    print("Connexion fermée")

