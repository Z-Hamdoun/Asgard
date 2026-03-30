from pymavlink_code.class_MAVLinCS import MAVLinCS
from Camera.class_Camera import Camera
from pymavlink import mavutil
from divers.class_Logger import Logger
from pnp.algo import PnPLandingSystem
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
        logger: Logger = Logger()):
        super().__init__(address, source_system, source_component, target_system, baud, timeout_heartbeat, send_automatic_timesync, timesync_delay, send_automatic_home_request, home_request_delay, sysid_to_request_home, pos_rate, dialect, logger)
        
    def precision_land(self):
        ...
        
    def loiter_pnp(self, gz_camera):
        while True:
            frame = gz_camera.get_frame(affiche=True)
            vector = pnp.get_landing_vector(frame, verbose=True)
            if vector:
                print("PNP DETECTE!!!!!!!!!!")
                self.send_landing_target(-vector[0], vector[1], vector[2])
            time.sleep(0.01)
    def loiter_pnp1(self, gz_camera):
        while True:
            frame = gz_camera.get_frame(affiche=True)
            vector = pnp.get_landing_vector(frame, verbose=True)
            if vector:
                print("PNP DETECTE!!!!!!!!!!!")
                dx, dy, current_z = vector
            
                # --- PARAMÈTRES ---
                target_z = 2.0  # Hauteur cible (2 mètres)
                kp_xy = 0.5     # Gain horizontal (Vitesse par mètre d'erreur)
                kp_z  = 1.0     # Gain vertical (Plus agressif pour tenir l'altitude)
                max_speed = 0.5 # Vitesse max (m/s) pour la sécurité

                # --- CALCUL DES VITESSES (Correcteur P) ---
            
                # 1. Vitesse Horizontale (Pour se centrer)
                vx = dx * kp_xy
                vy = dy * kp_xy
            
                # 2. Vitesse Verticale (Pour rester à 2m)
                # Si current_z (3m) > target_z (2m) -> Diff = 1m -> On doit descendre (Vitesse positive en NED)
                # Attention : En NED, Z positif = Vers le bas.
                # Donc : Vitesse Z = (Altitude Actuelle - Cible) * Gain
                error_z = current_z - target_z
                vz = error_z * kp_z

                # Saturation (Pour ne pas aller trop vite)
                vx = max(min(vx, max_speed), -max_speed)
                vy = max(min(vy, max_speed), -max_speed)
                vz = max(min(vz, max_speed), -max_speed)

                # --- ENVOI DE LA COMMANDE ---
                # Il faut envoyer ça dans le repère BODY (par rapport au nez du drone)
                # Ta classe MAVLinCS n'a pas de fonction set_speed_body par défaut, 
                # voici comment l'appeler directement :
            
                self.master.mav.set_position_target_local_ned_send(
                    0,                          # time_boot_ms
                    self.master.target_system, # target_system
                    self.master.target_component,
                    mavutil.mavlink.MAV_FRAME_BODY_OFFSET_NED, # <--- IMPORTANT : Repère BODY
                    0b110111000111,             # Mask: On ignore Position et Accel, on active VITESSE
                    0, 0, 0,                    # Pos X, Y, Z (Ignoré)
                    -vx, -vy, vz,                 # Vitesse X, Y, Z (Notre commande)
                    0, 0, 0,                    # Accel (Ignoré)
                    0, 0                        # Yaw
                )
            
                print(f"Correction: Alt={current_z:.2f}m -> Vz={vz:.2f} m/s")
            
                # Condition pour passer à l'étape suivante (Largage)
                # Si on est stable à 2m (+/- 10cm) et centré (+/- 5cm)
                if abs(error_z) < 0.10 and abs(dx) < 0.05 and abs(dy) < 0.05:
                    print("STAAAAABLE") # Transition vers l'état largage
            time.sleep(0.01)
    
    def loiter(self, gz_camera):
        while True:
            result = gz_camera.analyse(affichage=True)
            if result[-2] is not None:
                print('[Aruco] Going to AruCo marker')
                print(result[0], result[1], result[2])
                self.send_landing_target(result[0], result[1], result[2])
                
            time.sleep(0.01)


try:
    # Master drone
    drone0 = Drone(
        address="127.0.0.1:14550",
        source_system=201,
        source_component=mavutil.mavlink.MAV_COMP_ID_MISSIONPLANNER,
        target_system=1,
        baud=57600,
        timeout_heartbeat=None,
    )

    # Petit drone
    drone1 = Drone(
        address="127.0.0.1:14560",
        source_system=201,
        source_component=mavutil.mavlink.MAV_COMP_ID_MISSIONPLANNER,
        target_system=2,
        baud=57600,
        timeout_heartbeat=None,
    )

    # Gazebo Camera
    gz_camera = Camera(simulation='SITL', camera_topic="/world/iris_runway/model/drone1/model/gimbal/link/pitch_link/sensor/camera/image")
    
    # PNP
    pnp = PnPLandingSystem(laptop=True)

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

