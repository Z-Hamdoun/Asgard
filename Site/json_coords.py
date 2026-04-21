import json

DEFAULT_DASSAULT = {"lat_mission": 47.6013, "lng_mission": 2.0085}
DEFAULT_GIF = {"lat_mission": 48.7097, "lng_mission": 2.1671}


def charger_config():
    try:
        with open("config.json", "r") as fichier:
            config = json.load(fichier)
            return config
    except FileNotFoundError:
        print("Fichier de config introuvable, chargement des paramètres par défaut.")
        return DEFAULT_GIF


def sauvegarder_config(nouvelles_donnees):
    with open("config.json", "w") as fichier:
        json.dump(nouvelles_donnees, fichier, indent=4)


def default_dassault_config():
    return DEFAULT_DASSAULT


def default_gif_config():
    return DEFAULT_GIF
