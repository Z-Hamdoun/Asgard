**Structure du dossier**

divers/
├── class_Capteur_Position.py
├── class_Logger.py
├── drone_to_ned.py
├── geopy_fct.py
├── service.py
├── spirale.py
├── README.md
└── requirements.txt


# `class_Capteur_Position.py`  
Classe permettant d'obtenir la position x, y, z du drone sur Gazebo. La partie repérage réel (ex avec balises UWB) n'est pas implémenté, à vous de le faire.

# `class_Logger.py`  
Classe gérant les logs.

# `drone_to_ned.py`  
Conversion de coordonnées de vol drone vers le repère NED (North-East-Down).

# `geopy_fct.py`  
Fonctions utilisant la bibliothèque `geopy` pour calculs géographiques (distances, azimuts, etc.).

# `service.py`  
Fonction permettant de lancer un .service en arrière plan.

# `spirale.py`  
Générateur de trajectoire en spirale.

# 📄 `README.md`
Documentation.

# 📄 `requirements.txt`
Liste des dépendances Python nécessaires pour exécuter les codes.
