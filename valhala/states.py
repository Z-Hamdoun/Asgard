import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
import time
from divers.state_machine import State

class Idle(State):
    def on_enter(self, drone):
        print(f"[{drone.target_system}] En attente (Idle)...")

    def on_execute(self, drone):
        # Transition : Si le drone est armé, on décolle
        # Note: Dans ton code original tu armes manuellement. 
        # Ici on suppose qu'une fois armé, on veut passer au décollage.
        # Tu peux vérifier drone.motors_armed() si cette méthode existe dans MAVLinCS
        # Pour l'instant on force le passage pour l'exemple
        return Takeoff()

class Takeoff(State):
    def on_enter(self, drone):
        print(f"[{drone.target_system}] Décollage demandé à 3m")
        drone.takeoff(3) 
        self.start_time = time.time()

    def on_execute(self, drone):
        # Condition de sortie : On attend 10 secondes ou on vérifie l'altitude
        if time.time() - self.start_time > 10: 
            return SearchAruco()
        return self

class SearchAruco(State):
    """
    C'est ton ancienne fonction 'loiter' transformée en État.
    """
    def on_execute(self, drone):
        if drone.camera is None:
            print("Erreur: Pas de caméra assignée au drone")
            return self

        # Analyse d'une frame (ton code original)
        result = drone.camera.analyse(affichage=True)
        
        if result[-2] is not None:
            print(f'[{drone.target_system}] [Aruco] Tracking target: {result[0]}, {result[1]}')
            drone.send_landing_target(result[0], result[1], result[2])
            
            # Ici tu pourrais ajouter une logique :
            # Si on est bien aligné et bas -> return PrecisionLand()
        
        return self # On continue de chercher/tracker