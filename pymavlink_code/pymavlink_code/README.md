# Introduction

Pymavlink est une bibliothèque Python de bas niveau qui permet de communiquer avec un drone en utilisant le protocole MAVLink.  
Elle est utilisée comme fondation par de nombreuses autres bibliothèques (dont MAVProxy) et offre un accès direct aux messages MAVLink.

Contrairement à MAVSDK, pymavlink ne fournit pas de fonctions de haut niveau (comme *arm*, *takeoff*, etc.).  
Cela rend son usage plus complexe mais aussi beaucoup plus flexible : vous pouvez construire vos propres systèmes de communication, de contrôle ou de monitoring MAVLink, adaptés à vos besoins spécifiques.

Pymavlink s’installe facilement avec pip et peut être utilisé aussi bien pour dialoguer avec un simulateur (SITL, Gazebo, ArduPilot, PX4) que pour piloter un drone réel.

Toutes les informations sont disponibles dans la documentation officielle :  
[Doc Pymavlink](https://mavlink.io/en/mavgen_python/)

Le script `class_MAVLinCS.py` est fonctionnel sur ArduPilot uniquement. Si vous souhaitez transitionner vers PX4 en utilisant pymavlink, c'est possible, mais il faudra changer certaines lignes de code (notamment concernant les différents modes de vol et comment les interpréter).



**Structure du dossier**

pymavlink/
├── Exemples/
│   ├── drone.py
│   └── mission.py
├── class_MAVLinCS.py
├── class_Statustext_Receiver.py
├── class_Timesync_Handler.py
├── code_de_gestion_de_missions.py
├── README.md
└── requirements.txt


# 📁 Exemples

## `drone.py`
Exemple de takeoff/land classique.

## `mission.py`  
Contient les codes permettant d'envoyer une mission.



# `class_MAVLinCS.py`  
Classe permettant d'intéragir avec un ou plusieurs appareils MAVLink. Marche uniquement sur ArduPilot.

# `class_Statustext_Receiver.py`  
Classe dédiée à la réception et au traitement des messages `STATUSTEXT`.

# `class_Timesync_Handler.py`  
Gestion des synchronisations temporelles entre système de bord et station au sol.

# `code_de_gestion_de_missions.py`  
Définition des Codes de Gestion de Mission (CGM), utiles pour la communication entre stations au sol.



# 📄 `README.md`
Documentation.

# 📄 `requirements.txt`
Liste des dépendances Python nécessaires pour exécuter les codes.
