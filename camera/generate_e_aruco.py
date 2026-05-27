"""
Génère les textures PNG du marqueur e-ArUco pour Gazebo.

Structure physique :
  - Outer  : DICT_7X7_50 ID=5  (bit central noir, 61% surface noire) -- 35 cm
  - Inner  : DICT_4X4_50 ID=17 (75% surface noire)                  --  5 cm
  - Inner surélevé de 5 cm au-dessus de l'outer (plate-forme)

Justification des IDs (cf. Khazetdinov et al., SIBCON 2021 -- "Embedded ArUco") :
  - Outer ID=5 : seul ID avec bit central = noir ET ratio noir maximal (61.22%)
                 Le bit central noir crée la "zone d'emboîtement" pour l'inner.
  - Inner ID=17 : ratio de surface noire maximal dans DICT_4X4_50 (75%)
                  Maximise le contraste --> visible même depuis ~1 m.

Usage :
    python3 generate_e_aruco.py [--output /chemin/vers/models/e_aruco/materials/textures]
"""
import argparse
import cv2
import cv2.aruco as aruco
import numpy as np
from pathlib import Path

OUTER_DICT  = aruco.DICT_7X7_50
OUTER_ID    = 5
OUTER_SIZE  = 0.35   # m -- 7 × length_inner

INNER_DICT  = aruco.DICT_4X4_50
INNER_ID    = 17
INNER_SIZE  = 0.05   # m -- length_inner
INNER_Z     = 0.05   # m -- hauteur de la plate-forme


def make_marker_texture(dictionary, marker_id: int, total_px: int,
                        border_ratio: float = 0.10) -> np.ndarray:
    """Génère une image PNG du marqueur avec bordure blanche."""
    border_px = int(total_px * border_ratio)
    marker_px = total_px - 2 * border_px
    marker = aruco.generateImageMarker(dictionary, marker_id, marker_px)
    return cv2.copyMakeBorder(
        marker, border_px, border_px, border_px, border_px,
        cv2.BORDER_CONSTANT, value=255
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", default=None,
        help="Répertoire de sortie (défaut: ./textures/)"
    )
    args = parser.parse_args()

    out_dir = Path(args.output) if args.output else Path(__file__).parent / "textures"
    out_dir.mkdir(parents=True, exist_ok=True)

    dict_outer = aruco.getPredefinedDictionary(OUTER_DICT)
    dict_inner = aruco.getPredefinedDictionary(INNER_DICT)

    outer = make_marker_texture(dict_outer, OUTER_ID, total_px=1000)
    cv2.imwrite(str(out_dir / "outer_aruco.png"), outer)

    inner = make_marker_texture(dict_inner, INNER_ID, total_px=500)
    cv2.imwrite(str(out_dir / "inner_aruco.png"), inner)

    for fname, d, eid in [("outer_aruco.png", dict_outer, OUTER_ID),
                           ("inner_aruco.png", dict_inner, INNER_ID)]:
        img = cv2.imread(str(out_dir / fname), cv2.IMREAD_GRAYSCALE)
        det = aruco.ArucoDetector(d, aruco.DetectorParameters())
        _, ids, _ = det.detectMarkers(img)
        detected = ids.flatten().tolist() if ids is not None else []
        ok = eid in detected
        print(f"[{'OK' if ok else 'FAIL'}] {fname} --> IDs détectés: {detected}")


if __name__ == "__main__":
    main()
