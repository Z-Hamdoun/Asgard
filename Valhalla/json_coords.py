import json
import os

FICHIER_COORDS = "mission_coords.json"

def sauvegarder_config(coords_dict):
    """
    Sauvegarde le dictionnaire de coordonnées dans un fichier JSON local.
    """
    try:
        with open(FICHIER_COORDS, 'w', encoding='utf-8') as f:
            json.dump(coords_dict, f, indent=4)
        print(f"[JSON] Coordonnées sauvegardées avec succès : {coords_dict}")
        return True
    except Exception as e:
        print(f"[JSON] Erreur lors de la sauvegarde : {e}")
        return False

def lire_config():
    """
    Lit le fichier JSON et renvoie le dictionnaire. 
    Renvoie None si le fichier n'existe pas.
    """
    if not os.path.exists(FICHIER_COORDS):
        print(f"[JSON] Le fichier {FICHIER_COORDS} n'existe pas encore.")
        return None
    try:
        with open(FICHIER_COORDS, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[JSON] Erreur lors de la lecture : {e}")
        return None