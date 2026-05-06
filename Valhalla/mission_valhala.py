import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
import time
from Valhalla.src.class_Valhalla import Valhalla
import pymavlink_code.code_de_gestion_de_missions as CGM

def main():
    print("Démarrage de Valhalla...")
    
    # Connexion au contrôleur de vol
    valhalla = Valhalla(address="/dev/ttyAMA0", target_system=2)
    
    # Boucle de survie
    while True:
        valhalla.cgm.clear()
        
        print("Valhalla prêt. En attente d'un ordre du PC...")
        
        if valhalla.takeoff_pc(altitude=15):
            print("Décollage réussi ! Exécution de la suite...")
            
            # --- ICI tu mettras la suite ---
            # Exemple : valhalla.wait_for_gps_point_and_goto()
            
        else:
            print("Échec de la mission (Arrêt urgence ou Erreur).")
            # valhalla.change_mode("RTL") ou atterrissage d'urgence
            
        time.sleep(1) # Pause avant de réécouter une nouvelle mission

if __name__ == "__main__":
    main()