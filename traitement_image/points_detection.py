import cv2 as cv2
import numpy as np
import algo_pnp as pnp

def RT(frame, objectPoints, cameraMatrix,  distCoeffs = np.zeros(5), sensitivity = 0.5, n_points = 0):
    """
    Docstring de la fonction
    """
    # ---- Convert BGR → HSV ----
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # Threshold for magenta
    lower_magenta = np.array([140, 100, 150])
    upper_magenta = np.array([165, 255, 255])
    mask = cv2.inRange(hsv, lower_magenta, upper_magenta)

    mask = cv2.medianBlur(mask, 5)

    # Find contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    """
    Là c'est la galère : on peut imaginer qu'il y aura des artefacts... Et dans son code Kieron dit ouaiiiis
    si la tache est plus grande que 50 (???) ça paaaasse mais en ft c'est super random, si le drone 
    s'éloigne ça marche plus et c'est caca
    Donc à la place on calcule la taille moyenne des tâches et on dit qu'une tâche est acceptable si elle dépasse
    en rayon un certain pourcentage de cette moyenne, caractérisé par sensitivity

    Autre solution implémentée : on peut simplement fournir le nb de points souhaité et on choisit les tâches
    les plus brillantes
    """
    
    if n_points == 0 : 
        points = []
        areas = [cv2.contourArea(c) for c in contours]
        for c in contours:
                if cv2.contourArea(c) >= sensitivity * np.mean(areas) :
                    points.append(c)
    else :
         #Comme on connait n_pts on prend juste les n_points tâches les plus brillantes
         points_sorted = sorted(contours, key=cv2.contourArea, reverse=True)
         if len(points) >= n_points :
            points = points_sorted[:n_points]
    
    imagePoints = np.array([[cv2.minEnclosingCircle(c)[0],cv2.minEnclosingCircle(c)[1]] for c in points])

    tvec,rvec = pnp.PNP(objectPoints, imagePoints, cameraMatrix, distCoeffs)

    R,_ = cv2.Rodrigues(rvec)
    """
    On a la relation :      Xcam = R*Xmonde + tvec
    Donc :                  Xmonde = R.T * (Xcam - tvec)
    """
    V = R.T*tvec