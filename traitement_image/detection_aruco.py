import cv2
import numpy as np

"""
Attention changer de source : source ~/envs/cacs-env/bin/activate

Conclusion d'une longue discussion avec chat gpt :

        - beaucoup de problèmes liés à la cohabitation de différentes versions d'opencv, qui n
        nécessitent ici l'utilisation du venv

        - le code de détection ne fonctionne pas pour des images trop nettes ! Pas la peine de
        lui passer en argument un beau code aruco généré apr le pc ça ne fonctionne pas, il
        faut une photo

        -attention à la taille de l'image
"""

image = "exemple_aruco.jpg"
# Dictionnaire ArUco
dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)

# Relire l'image pour simuler la capture réelle
img = cv2.imread(image, cv2.IMREAD_GRAYSCALE)
target_size = 200
img_resized = cv2.resize(img, (target_size, target_size), interpolation=cv2.INTER_NEAREST)

# Création du détecteur
detector = cv2.aruco.ArucoDetector(dictionary)

# Détection
markerCorners, markerIds, rejectedCandidates = detector.detectMarkers(img_resized)

print("Detected IDs:", markerIds)
print("Corners:", markerCorners)

def détection_aruco(image, dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)) :
    detector = cv2.aruco.ArucoDetector(dictionary)
    return detector.detectMarkers(img_resized)
