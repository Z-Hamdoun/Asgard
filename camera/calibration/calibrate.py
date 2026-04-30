import numpy as np
import cv2
import glob
import os

# ==============================================================================
# CONFIGURATION DE VOTRE DAMIER (À MODIFIER SELON VOTRE IMPRESSION)
# ==============================================================================
# Nombre d'intersections intérieures (Colonnes, Lignes)
# Exemple : Un damier de 10x7 cases aura 9x6 intersections.
CHESSBOARD_SIZE = (9, 6) 

# Taille réelle d'un côté d'un carré imprimé (en mètres). 
# Mesurez au millimètre près avec une règle !
SQUARE_SIZE = 0.028 # Exemple: 2.5 cm = 0.025m

# Dossier contenant les photos prises par la RPi Camera (ex: .jpg, .png)
IMAGE_FOLDER = 'images_calib/*.jpg' 
# ==============================================================================

def main():
    print("--- OUTIL DE CALIBRATION DE CAMÉRA ---")
    
    # Critères d'arrêt pour l'optimisation sub-pixel (précision extrême)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

    # Préparation des points 3D du monde réel (0,0,0), (1,0,0), (2,0,0) ...
    objp = np.zeros((CHESSBOARD_SIZE[0] * CHESSBOARD_SIZE[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:CHESSBOARD_SIZE[0], 0:CHESSBOARD_SIZE[1]].T.reshape(-1, 2)
    objp = objp * SQUARE_SIZE

    # Tableaux pour stocker les points 3D (monde) et 2D (image) de toutes les images
    objpoints = [] # Points 3D dans le monde réel
    imgpoints = [] # Points 2D dans l'image

    images = glob.glob(IMAGE_FOLDER)
    
    if len(images) == 0:
        print(f"[ERREUR] Aucune image trouvée dans {IMAGE_FOLDER}")
        print("Prenez 15-30 photos d'un damier plat et placez-les dans ce dossier.")
        return

    print(f"[INFO] {len(images)} images trouvées. Début de l'analyse...")

    img_shape = None
    success_count = 0

    for fname in images:
        img = cv2.imread(fname)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # On sauvegarde la résolution de l'image (doit être constante)
        if img_shape is None:
            img_shape = gray.shape[::-1]

        # Chercher les coins du damier
        ret, corners = cv2.findChessboardCorners(gray, CHESSBOARD_SIZE, None)

        # Si le damier est trouvé, on affine la précision et on stocke
        if ret == True:
            objpoints.append(objp)
            
            # Affinement Sub-Pixel (Crucial pour la précision PnP)
            corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            imgpoints.append(corners2)
            success_count += 1
            
            # Affichage visuel (facultatif)
            #cv2.drawChessboardCorners(img, CHESSBOARD_SIZE, corners2, ret)
            #cv2.imshow('Damier detecte', img)
            #cv2.waitKey(100) # Montre l'image pendant 100ms
        else:
            print(f"[ATTENTION] Damier non détecté sur l'image : {fname}")

    #cv2.destroyAllWindows()

    if success_count < 10:
        print(f"\n[ERREUR CRITIQUE] Seulement {success_count} images valides.")
        print("Il faut au minimum 10-15 bonnes images pour une calibration correcte.")
        return

    print(f"\n[INFO] Calcul de la matrice avec {success_count} images valides... Patientez.")

    # LA FONCTION MAGIQUE DE CALIBRATION
    ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, img_shape, None, None)

    print("\n" + "="*60)
    print("🎯 RÉSULTATS DE LA CALIBRATION (À COPIER/COLLER)")
    print("="*60 + "\n")
    
    print(f"Erreur de Reprojection (RMSE) : {ret:.4f} pixels")
    if ret < 0.5:
        print(" -> EXCELLENT ! La calibration est ultra-précise.")
    elif ret < 1.0:
        print(" -> ACCEPTABLE. Bon pour le vol.")
    else:
        print(" -> MAUVAIS. Refaites des photos avec un damier plus plat.")

    print("\n# === À COLLER DANS TON CODE PYTHON (Camera.py ou pnp_landing.py) ===")
    print("self._camera_matrix = np.array([")
    print(f"    [{mtx[0][0]:.5f}, {mtx[0][1]:.5f}, {mtx[0][2]:.5f}],")
    print(f"    [{mtx[1][0]:.5f}, {mtx[1][1]:.5f}, {mtx[1][2]:.5f}],")
    print(f"    [{mtx[2][0]:.5f}, {mtx[2][1]:.5f}, {mtx[2][2]:.5f}]")
    print("], dtype=np.float64)")
    print("")
    print(f"self._dist_coeffs = np.array([{dist[0][0]:.5f}, {dist[0][1]:.5f}, {dist[0][2]:.5f}, {dist[0][3]:.5f}, {dist[0][4]:.5f}], dtype=np.float64)")
    print("=======================================================================\n")

if __name__ == '__main__':
    main()
