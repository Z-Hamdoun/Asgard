import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
import time

from divers.state_machine import State

class InitPhase(State):
    """
    Super-etat INIT
    """

class Connect(InitPhase):
    def on_enter(self, drone):
        drone.logger.log("[CONNECT] Waiting for HEARTBEAT...")
    
    def on_execute(self, drone):
        drone.master.wait_heartbeat()
        drone.logger.log("[SUCCESS][CONNECT] Drone connected!")
        return Arm()

class Arm(InitPhase):
    def on_enter(self, drone):
        drone.logger.log("[ARMING] Arming drone...")
        self.armed = drone.arm()
    
    def on_execute(self, drone):
        if not self.armed:
            return Wait(5)
        else:
            drone.logger.log("[SUCCESS][ARMING] Drone armed!")
            return TakeOff(3)

class Wait(InitPhase):
    def __init__(self, duration):
        super().__init__()
        self.duration = duration
        
    def on_enter(self, drone):
        drone.logger.log(f"[WAIT] Waiting {self.duration} s before re-arming...")
    
    def on_execute(self, drone):
        time.sleep(self.duration)
        return Arm()

class TakeOff(State):
    def __init__(self, alt):
        super().__init__()
        self.alt = alt
    def on_enter(self, drone):
        drone.logger.log("[TAKEOFF] Taking off...")
        self.alt_reached = drone.takeoff(self.alt)
    
    def on_execute(self, drone):
        if self.alt_reached:
            drone.logger.log("[SUCCESS][TAKEOFF] Altitude reached!")
            return ReachAlt()
        else:
            drone.logger.log("[FAIL][TAKEOFF] Retrying...")
            return TakeOff(self.alt)

class ReachAlt(State):
    def on_enter(self, drone):
        drone.logger.log("[REACH_ALT] Waiting for commands...")
    
    def on_execute(self, drone):
        return FindAruco()

class FindAruco(State):
    def on_enter(self, drone):
        drone.logger.log("[ARUCO] Looking for AruCo")
    
    def on_execute(self, drone):
        result = drone.camera.analyse(affichage=True)
        if result[-2] is not None:
            drone.logger.log('[ARUCO] Aruco found! Going to AruCo marker')
            drone.send_landing_target(result[0], result[1], result[2])
        
        return self

Idle = Connect
