**Principe**

C'est une classe qui peut être utilisée à la fois pour une Pi Camera et à la fois pour une simulation Gazebo (voir rapport de passation dassault 2024-2025)

**Structure du dossier**

Camera/
├── class_Camera.py
├── find_GazeboCamera_caracteristics.py
├── README.md
└── requirements.txt


# `class_Camera.py`  
Classe de gestion de la caméra.

# `find_GazeboCamera_caracteristics.py`  
Trouver les matrices et la résolution de la caméra sous Gazebo.

# 📄 `README.md`
Documentation.

# 📄 `requirements.txt`
Liste des dépendances Python nécessaires pour exécuter les codes.

# `camera_stream.py`
Ce fichier permet de tester en temps reel la camera RPI avec un streaming udp (plus rapide qu'un site web).

## Sur l'ordinateur:
```sh
sudo apt install ffmpeg 
```

### Attendre le stream:

```sh
ffplay -fflags nobuffer -flags low_delay -framedrop udp://0.0.0.0:5000
```

### Trouver l'adress IP du pc:
```sh
hostname -I
```
ou bien

```sh
ip route get 1.1.1.1 | awk '{print $7}'
```

## Sur la RPI:
```sh
venv
python Camera/camera_stream.py --ip \[adress IP du pc\] --port \[optional\]
```



