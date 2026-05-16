import cv2
import cv2.aruco as aruco
import numpy as np

def generate_pure_earuco():
    print("--- Génération e-ArUco (Méthode Univ. Kazan) ---")
    
    # 1. Un SEUL dictionnaire pour tout le système
    dict_7x7 = aruco.getPredefinedDictionary(aruco.DICT_7X7_50)
    
    # Dimensions : 9x9 blocs au total (7x7 data + 2 bordure)
    pixels_per_block = 100 
    img_size = 9 * pixels_per_block # 900x900
    
    # -------------------------------------------------------------
    # ETAPE A : Trouver le meilleur petit marqueur (Maximum de Noir)
    # -------------------------------------------------------------
    best_inner_id = 0
    max_black_pixels = 0
    
    for i in range(50):
        marker = aruco.generateImageMarker(dict_7x7, i, 900)
        # On compte les pixels noirs (valeur 0)
        black_count = np.sum(marker == 0)
        if black_count > max_black_pixels:
            max_black_pixels = black_count
            best_inner_id = i
            
    inner_img = aruco.generateImageMarker(dict_7x7, best_inner_id, pixels_per_block)
    print(f"✅ ID Petit Marqueur (Max Noir) : {best_inner_id}")

    # -------------------------------------------------------------
    # ETAPE B : Trouver le grand marqueur (Centre Noir)
    # -------------------------------------------------------------
    best_outer_id = -1
    outer_img = None
    
    for i in range(500):
        if i == best_inner_id: 
            continue # On ne veut pas le même ID
            
        marker = aruco.generateImageMarker(dict_7x7, i, img_size)
        # Le centre de l'image (pixel 450, 450) doit être noir
        if marker[450, 450] == 0:
            best_outer_id = i
            outer_img = marker
            break
            
    print(f"✅ ID Grand Marqueur (Centre Noir) : {best_outer_id}")

    # -------------------------------------------------------------
    # ETAPE C : Fusion (L'illusion optique)
    # -------------------------------------------------------------
    e_aruco_img = outer_img.copy()
    
    # Remplacement du bloc central exact par le petit marqueur
    start_idx = 4 * pixels_per_block
    end_idx = 5 * pixels_per_block
    e_aruco_img[start_idx:end_idx, start_idx:end_idx] = inner_img

    # Ajout de la bordure blanche obligatoire pour OpenCV
    padded_img = cv2.copyMakeBorder(e_aruco_img, 50, 50, 50, 50, cv2.BORDER_CONSTANT, value=255)
    
    cv2.imwrite("e_aruco.png", padded_img)
    print("✅ Fichier 'e_aruco.png' généré avec succès ! Remplacez l'ancien dans Gazebo.")

if __name__ == "__main__":
    generate_pure_earuco()