import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from class_Drone import Drone
from pymavlink import mavutil
import time

from threading import Thread


def send_rc(drone):
    drone.master.mav.rc_channels_override_send(
            drone.master.target_system,
            drone.master.target_component,
            65535, 65535, 1500, 65535,
            65535, 65535, 65535, 65535
        )
    time.sleep(0.1)

def activate_prec(drone, val):
    drone.master.mav.rc_channels_override_send(
            drone.master.target_system,
            drone.master.target_component,
            65535, 65535, 65535, 65535,
            65535, 65535, 65535, val
        )
    msg = drone.get_msg(msg_type='RC_CHANNELS')
    
    if msg:
        rc8_value = msg.chan8_raw
        print(f"Valeur RC: {rc8_value}")
    time.sleep(0.05)


try:
    drone = Drone(
        address="/dev/ttyAMA0",
        source_component=mavutil.mavlink.MAV_COMP_ID_ONBOARD_COMPUTER,
        target_system=1,
        baud=921600,
    )
    rc_thread = Thread(target=send_rc, args=(drone, ), daemon=True)


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
            rc_thread.start()
            success = drone.change_mode("FLOWHOLD")
            print(success)
            rc_thread.join()
            drone.change_mode("LAND")
        
        elif inpt == "land":
            success = drone.change_mode("LAND")
            print(success)
        
        elif inpt == "precland":
            loit = Thread(target=drone.loiter, )
            loit.start()
        
        elif inpt == "onprec":
            val = int(input("Valeur RC: "))
            acti = Thread(target=activate_prec, args=(drone, val))
            acti.start()
        
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

