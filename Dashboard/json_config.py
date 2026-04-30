import json

DEFAULT={"vrai_largage": True,
"taille_quadrilllage":10,
"pas_quadrillage":2,
"radius_acceptance":1,
"FOLLOW_MAX_SPEED":1400,
"alt_quadrillage":8}

def charger_config():
    try:
        with open("config.json", "r") as fichier:
            config = json.load(fichier)
            return config
    except FileNotFoundError:
        print("Fichier de config introuvable, chargement des paramètres par défaut.")
        return DEFAULT

def sauvegarder_config(nouvelles_donnees):
    with open("config.json", "w") as fichier:
        json.dump(nouvelles_donnees, fichier, indent=4)

def default_config():
    return DEFAULT
