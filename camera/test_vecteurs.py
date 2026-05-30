import sys, os, time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Imports depuis les vrais modules Valkyrie (même code qu'en mission)
from Valkyrie.vision.class_Camera import Camera
from pnp.algo import PnPLandingSystem

# ============================================================
#  CHOIX DU MODE
#  "analyse"   : ArUco classique  (DICT_4X4_250)
#  "e_analyse" : e-ArUco double marqueur (inner 4x4 + outer 7x7)
#  "pnp"       : PnP sur les 4 marqueurs circulaires de Valhalla
# ============================================================
MODE = "e_analyse"

# True = matrice wide-angle, False = matrice standard
CAMERA_WIDE = False

# Distance entre les marqueurs PnP (côté du carré, en mètres)
PNP_MARKER_DISTANCE_M = 0.33

# ============================================================

camera = Camera(simulation=None, wide=CAMERA_WIDE)

if MODE == "pnp":
    pnp = PnPLandingSystem(
        marker_distance=PNP_MARKER_DISTANCE_M,
        camera_matrix=camera._camera_matrix,
        dist_coeffs=camera._dist_coeffs,
    )

fx = camera._camera_matrix[0, 0]
print(f"Mode     : {MODE}")
print(f"Camera   : fx={fx:.1f}  {'WIDE' if CAMERA_WIDE else 'STANDARD'}")
print(f"{'─' * 60}")
print(f"{'État':<12} {'dx (m)':>10} {'dy (m)':>10} {'dz (m)':>10}  info")
print(f"{'─' * 60}")

try:
    while True:
        t0 = time.time()

        if MODE == "analyse":
            dx, dy, dz, info, _ = camera.analyse(affichage=False)

        elif MODE == "e_analyse":
            dx, dy, dz, info, _ = camera.analyse_e_aruco(affichage=False)

        elif MODE == "pnp":
            frame = camera.get_frame(timeout=2)
            if frame is None:
                print("Pas de frame".ljust(70), end="\r")
                continue
            result = pnp.get_landing_vector(frame)
            if isinstance(result, tuple) and len(result) == 3 and isinstance(result[0], float):
                dx, dy, dz = result
                info = "PnP OK"
            else:
                dx, dy, dz, info = 0.0, 0.0, 0.0, None

        else:
            raise ValueError(f"MODE inconnu : '{MODE}'  (valeurs : analyse / e_analyse / pnp)")

        dt_ms = (time.time() - t0) * 1000

        if info is not None:
            ligne = f"{'DÉTECTÉ':<12} {dx:>+10.3f} {dy:>+10.3f} {dz:>+10.3f}  {info}  [{dt_ms:.0f}ms]"
        else:
            ligne = f"{'---':<12} {'':>10} {'':>10} {'':>10}  [{dt_ms:.0f}ms]"

        print(ligne.ljust(80), end="\r")

except KeyboardInterrupt:
    print("\nArrêt.")
    camera.close()
