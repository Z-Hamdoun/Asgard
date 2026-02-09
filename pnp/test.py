import cv2
import numpy as np
import sys
import os
import time

# --- IMPORT DE TON CODE ---
# Ajoute le dossier parent au path pour pouvoir importer 'vision'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
from pnp.algo import PnPLandingSystem

# --- FONCTION UTILITAIRE POUR LES SLIDERS ---
def nothing(x):
    pass

def main():
    print("--- BANC D'ESSAI PNP (ROBUSTE) ---")
    print("1. Ajustez les sliders pour isoler les points.")
    print("2. Le masque affiché inclut le nettoyage (Erode/Dilate).")
    print("3. Seuls les 5 plus gros points sont entourés en VERT.")

    # 1. SETUP
    # IMPORTANT : Mets ici la taille réelle de ton carré de test (en mètres)
    cote_carre = 0.16 # ex: 20cm pour le test sur feuille A4
    pnp = PnPLandingSystem(marker_distance=cote_carre)
    
    cap = cv2.VideoCapture(0) # Ta webcam

    # 2. FENÊTRE DE RÉGLAGE (Trackbars)
    cv2.namedWindow("Calibrage Couleur")
    
    # --- PRESETS DE COULEURS ---
    # OPTION 1 : ROUGE (Défaut)
    h1_min_def, h1_max_def = 0, 10
    h2_min_def, h2_max_def = 170, 179
    
    # OPTION 2 : ROSE FLUO (Décommenter pour tester)
    # h1_min_def, h1_max_def = 145, 170
    # h2_min_def, h2_max_def = 145, 170 

    # Plage 1
    cv2.createTrackbar("H1 Min", "Calibrage Couleur", h1_min_def, 179, nothing)
    cv2.createTrackbar("H1 Max", "Calibrage Couleur", h1_max_def, 179, nothing)
    # Plage 2 (Utile surtout pour le Rouge)
    cv2.createTrackbar("H2 Min", "Calibrage Couleur", h2_min_def, 179, nothing)
    cv2.createTrackbar("H2 Max", "Calibrage Couleur", h2_max_def, 179, nothing)
    # Saturation / Valeur (Commun aux deux)
    cv2.createTrackbar("S Min", "Calibrage Couleur", 100, 255, nothing) 
    cv2.createTrackbar("V Min", "Calibrage Couleur", 50, 255, nothing)

    while True:
        ret, frame = cap.read()
        if not ret: break

        # --- A. MISE A JOUR DES PARAMETRES ---
        h1_min = cv2.getTrackbarPos("H1 Min", "Calibrage Couleur")
        h1_max = cv2.getTrackbarPos("H1 Max", "Calibrage Couleur")
        h2_min = cv2.getTrackbarPos("H2 Min", "Calibrage Couleur")
        h2_max = cv2.getTrackbarPos("H2 Max", "Calibrage Couleur")
        s_min = cv2.getTrackbarPos("S Min", "Calibrage Couleur")
        v_min = cv2.getTrackbarPos("V Min", "Calibrage Couleur")

        # Injection directe dans l'instance
        pnp.lower_hsv1 = np.array([h1_min, s_min, v_min])
        pnp.upper_hsv1 = np.array([h1_max, 255, 255])
        pnp.lower_hsv2 = np.array([h2_min, s_min, v_min])
        pnp.upper_hsv2 = np.array([h2_max, 255, 255])

        # --- B. APPEL DE TON ALGO ---
        vector = pnp.get_landing_vector(frame)

        # --- C. VISUALISATION DU MASQUE NETTOYÉ ---
        # On reproduit exactement ce que fait l'algo interne
        blurred = cv2.GaussianBlur(frame, (5, 5), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, pnp.lower_hsv1, pnp.upper_hsv1) + \
               cv2.inRange(hsv, pnp.lower_hsv2, pnp.upper_hsv2)
        
        # LE NETTOYAGE : C'est ça qui recolle les morceaux !
        mask = cv2.erode(mask, None, iterations=2)
        mask = cv2.dilate(mask, None, iterations=2)
        
        # --- D. DESSIN DES CONTOURS FILTRÉS ---
        # On redétecte pour afficher ce que l'algo voit
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # On trie pour ne garder que les 5 plus gros (comme l'algo)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

        if vector:
            dx, dy, dz = vector
            color = (0, 255, 0) # Vert
            
            # Dessin des contours validés en VERT
            cv2.drawContours(frame, contours, -1, color, 3)
            
            text_x = f"X: {dx*100:.1f} cm"
            text_y = f"Y: {dy*100:.1f} cm"
            text_z = f"Z: {dz*100:.1f} cm"
            
            cv2.putText(frame, "LOCK CONFIRME", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
            cv2.putText(frame, text_x, (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            cv2.putText(frame, text_y, (20, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            cv2.putText(frame, text_z, (20, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

            # Réticule
            h, w, _ = frame.shape
            cx, cy = w // 2, h // 2
            pixel_scale = 3000 / (dz + 0.1)
            tx = int(cx + (dy * pixel_scale))
            ty = int(cy - (dx * pixel_scale))
            cv2.line(frame, (cx, cy), (tx, ty), (0,255,255), 2)
            cv2.circle(frame, (tx, ty), 10, (0,0,255), -1)

        else:
            cv2.putText(frame, "RECHERCHE...", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            # Dessin des contours candidats en ROUGE
            cv2.drawContours(frame, contours, -1, (0, 0, 255), 2)
            cv2.putText(frame, f"Candidats: {len(contours)}/5", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)

        cv2.imshow("Vue Drone", frame)
        cv2.imshow("Masque Nettoye", mask)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()