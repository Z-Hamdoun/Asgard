import cv2
import numpy as np

def PNP(
        objectPoints : np.array, 
        imagePoints : np.array, 
        camMatrix = np.array([
                            [800,0,320],
                            [0,800,240],
                            [0,0,1]], 
                            dtype = np.float64), 
        distCoeffs = np.zeros(5),
        flags = cv2.SOLVEPNP_ITERATIVE
        ) -> tuple:
    
    """
    This function returns given an array of exactly 4 real 3D points and the array of their projections on an image
    the couple (T,R), where T is the translation vector and R the rotation vector
    
    :param objectPoints: np.array with the 3D coordinates of the real 3D points
    :type objectPoints: np.array with the 2D coordinates of the projected 2D points
    :param imagePoints: Description
    :type imagePoints: np.array
    :param camMatrix: Description
    :param distCoeffs: Description
    :param flags: Description
    :return: Description
    :rtype: tuple
    """
    ok, rvec, tvec = cv2.solvePnP(
                                    objectPoints,
                                    imagePoints,
                                    camMatrix,
                                    distCoeffs,
                                    flags
                                )
    return (tvec,rvec)

if __name__ == "__main__" : 
    #Points 3D "réels"
    O = np.array([
        [0,0,0],
        [1,0,0],
        [1,1,0],
        [0,1,0]
        ], dtype = np.float32)

    #Points 2D projection sur l'image des points réels
    I = np.array([
        [320,240],
        [400,240],
        [400,320],
        [320,320]
    ], dtype = np.float32)

    #Matrice de la caméra
    C = np.array([
        [800,0,320],
        [0,800,240],
        [0,0,1]], 
        dtype = np.float64)

    #Distorsion nulle
    D = np.zeros(5)

    T,R = PNP(O,I,C,D)
    print("matrice de translation : ")
    print(T)
    print("Matrice de rotation : ")
    print(R)