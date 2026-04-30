import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
import time
from utils.state_machine import State


class FailSafe(State):
    """
    Etat critique: on arrete tout et on decide quoi faire pour ne pas endommager le drone
    """
    
    def on_enter(self, drone):
        log_msg = "[FAILSAFE] Aborting!!!!"
        if drone.logger is not None:
            drone.logger.log(log_msg)
    
    def on_execute(self, drone):
        # ici on ne fait qu'observer l'atterissage
        return self


class MissionState(State):
    """
    Classe generique definissant un etat.
    """
    
    def check_failsafes(self, drone):
        """
        Verifie les conditions d'erreur globales
        """
        return None
    
    def on_execute(self, drone):
        return self.check_failsafes(drone)


class InitPhase(MissionState):
    """
    Super-etat pour le groupe INIT.
    Sert à regrouper WaitForGps et Arming.
    """
    
class WaitForGPS(InitPhase):
    def on_enter(self, drone):
        log_msg = "[INIT] Waiting for GPS..."
        if drone.logger is not None:
            drone.logger.log(log_msg)
    
    def on_execute(self, drone):
        if drone.gps_fix():
            return Arming()
        return self
    

class Arming(InitPhase):
    
    def on_enter(self, drone):
        drone.arm(timeout_arming=0)
    
    def on_execute(self, drone):
        if super().on_execute(drone):
            return super().on_execute(drone)
        if drone.motors_armed():
            drone.logger.log('[ARMING] Drone Armed!')
            return Takeoff()

        return self


class Takeoff(MissionState):

    def on_enter(self, drone):
        self.target_alt = 3
        drone.takeoff(self.target_alt, timeout_takeoff=0)
        self.start_time = time.time()
    
    def on_execute(self, drone):
        if super().on_execute(drone):
            return super().on_execute(drone)
        #if time.time() - self.start_time > 2000:
            print(f"[{drone.target_system}] Erreur: Timeout au décollage !")
            # return FailSafe()
            return self
        
        _, _, rel_alt, _ = drone.position()
        print(rel_alt)
        
        # A remplacer
        if rel_alt is not None and rel_alt >= (self.target_alt * 0.5):
            print(f"[{drone.target_system}] Altitude {rel_alt}m atteinte.")
            return ReachDest()
            
        return self

class ReachDest(MissionState):
    def on_enter(self, drone):
        print(f"[{drone.target_system}] Navigation vers la destination...")
        drone.land()

    def on_execute(self, drone):
        if super().on_execute(drone): return super().on_execute(drone)
        
        # Test
        if 0 < 1.0:
            return Communicate()
            
        return self


class Communicate(MissionState):
    def on_enter(self, drone):
        print(f"[{drone.target_system}] En attente du drone pair (Communicate)...")

    def on_execute(self, drone):
        if super().on_execute(drone): return super().on_execute(drone)

        # Simulation
        peer_ready = True 
        if peer_ready:
            return Stabilize()
        return self

class Stabilize(MissionState):
    def on_execute(self, drone):
        if super().on_execute(drone): return super().on_execute(drone)
        
        print(f"[{drone.target_system}] Stabilisation finale & RTL")
        return RTL()

class RTL(MissionState):
    def on_enter(self, drone):
        print(f"[{drone.target_system}] Retour à la maison.")
        drone.return_to_launch(timeout=0) # Non bloquant

    def on_execute(self, drone):
        if drone.motors_disarmed():
            print(f"[{drone.target_system}] Mission Terminée")
            return None # Fin de la FSM
        return self

Idle = WaitForGPS