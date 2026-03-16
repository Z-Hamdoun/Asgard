from dataclasses import dataclass
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import time
import math
import sys
import os

# Get the absolute path to the project directory
current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.append(project_dir)
#sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from webserver.action import ACTION_CONNEXTION, AIRCRAFT_ID, DRONE_ID
from webserver.models import *

# Define the database path
db_path = os.path.join(current_dir, 'instance', 'missions.db')
db_uri = f"sqlite:///{db_path}"

engine = create_engine(db_uri)
Session = sessionmaker(bind=engine)
db = Session()

class WebServerListener:
    def __init__(self, db_uri=db_uri):
        """Initialise la connexion à la base de données et vide les actions existantes."""
        # Ensure the instance directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        # Suppression des actions en attente
        db.query(ActionRequest).delete()
        db.commit()

    def take_action(self) -> dict | None:
        """
        Récupère et supprime une action en attente.
        Retourne l'action sous forme de dictionnaire ou None s'il n'y a aucune action.
        """
        action = db.query(ActionRequest).first()

        if action:
            action_data = {
                "id": action.id,
                "aircraft_id": action.object_id,
                "action": action.action_id
            }
            db.delete(action)
            db.commit()
            return action_data

        return None  # Aucune action disponible
    
    def get_all_parameters(self):
        parameters = db.query(Parameter).all()
        return [param.to_dict() for param in parameters]

    def get_all_gps_points(self) -> list | None:
        """
        Récupère et supprime une action en attente.
        Retourne l'action sous forme de dictionnaire ou None s'il n'y a aucune action.
        """
        parameters = db.query(Marker).order_by(Marker.seq).all()
        return [param.to_dict() for param in parameters]

    def close(self):
        """Ferme la session proprement."""
        db.close()


class PosUsrFollowMe:
    def __init__(self):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self.engine = create_engine(db_uri)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

        # Suppression des actions en attente
        self.session.query(UsrPosFollowMe).delete()
        self.session.commit()

        self.latitude = None
        self.longitude = None
        self.time_last_value = 0

    def get_updated_value(self) -> dict | None:
        pos_usr = self.session.query(UsrPosFollowMe).first() # point de largage
        # timeout = 5 # seconded
        if pos_usr.latitude is None: # time.time() > pos_usr["timestamp"] + timeout or 
            return {"msg": "disconnected"}
        else:
            return {"latitude":pos_usr.latitude, "longitude":pos_usr.longitude, "altitude":pos_usr.altitude, "msg":"OK", "age":time.time() - pos_usr.timestamp}



import requests

def update_button_permission(object_id, action_id, allowed):
    
    # update or add permission in db if not exists
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post("http://127.0.0.1:5000/api/update_button_permission", json={"object_id": object_id, "action_id": action_id, "allowed": allowed}, headers=headers, timeout=1)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print("Erreur lors de la requête:", e)

def send_gps_position(object_id, position):
    """
    Envoie la position GPS d'un véhicule à l'API Flask.

    Args:
        object_id (int): L'id de l'objet.
        position (tuple:fload): Lat, lon, altitude du véhicule sous forme de tuple (lat, lon, altitude).
    
    """

    payload = {
        "object_id": object_id,
        "latitude": position[0],
        "longitude": position[1],
        "altitude": position[2]
    }
    
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post("http://127.0.0.1:5000/api/set_coordinates", json=payload, headers=headers, timeout=1)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print("Erreur lors de la requête:", e)

def add_log(message,level):
    # add log in db
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post("http://127.0.0.1:5000/api/add_log", json={"message": message, "level": level}, headers=headers, timeout=1)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print("Erreur lors de la requête:", e)
    
@dataclass
class Status:
    object_id: int
    label: str
    value: str
    color: str

def update_status(status: list[Status]):
    
    payload = [
        {
            "id": s.object_id,
            "label": s.label,
            "valeur": s.value,
            "couleur": s.color
        }
        for s in status
    ]
    
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post("http://127.0.0.1:5000/api/send_status", json=payload, headers=headers, timeout=1)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        error_msg = f"Erreur lors de l'envoi des statuts : {e}"
        print(error_msg)

def update_batterie(object_id: int,batterie: int):

    color = "green"

    status_list = [
        Status(object_id=object_id, label="Batterie", value=f"{batterie}V", color=color),
    ]

    update_status(status_list)

def update_connected(object_id: int, system_type: str, is_connected: bool):
    color = "green" if is_connected else "red"
    connected = "Connected" if is_connected else "Disconnected"

    status_list = [
        Status(object_id=object_id, label=system_type, value=connected, color=color),
    ]

    update_status(status_list)

def update_armed(object_id: int, is_armed: bool):
    color = "green" if is_armed else "red"
    armed = "Armed" if is_armed else "Disarmed"

    status_list = [
        Status(object_id=object_id, label="Armed", value=armed, color=color),
    ]

    update_status(status_list)

def update_mode(object_id: int, mode: str):
    color = "blue"

    status_list = [
        Status(object_id=object_id, label="Mode", value=mode, color=color),
    ]

    update_status(status_list)

if __name__ == "__main__":
    print(f"Database path: {db_path}")
    
    # Créer une table de test pour vérifier la connexion à la base de données
    try:
        test_engine = create_engine(db_uri)
        from sqlalchemy import Table, Column, Integer, String, MetaData
        metadata = MetaData()
        test_table = Table('test_connection', metadata,
            Column('id', Integer, primary_key=True),
            Column('message', String)
        )
        metadata.create_all(test_engine)
        print("Connexion à la base de données réussie - table de test créée")
    except Exception as e:
        print(f"ERREUR lors du test de connexion à la base de données: {e}")
        import traceback
        traceback.print_exc()
    
    listener = WebServerListener()
    
    add_log("Système de surveillance des marqueurs et chemins démarré", "INFO")
    print("Système de surveillance démarré - en attente d'actions...")

    t = 0

    while True:
        action = listener.take_action()

        drone_position = [48.69903368823523 + math.sin(t/10)/100, 2.1814727783203130 + math.cos(t/10)/100, 100]
        send_gps_position(DRONE_ID, drone_position)

        plane_position = [48.69903368823523 + math.sin(-t/10)/110, 2.1814727783203130 + math.cos(-t/10)/110, 100]
        send_gps_position(AIRCRAFT_ID, plane_position)

        t += 1

        if action:

            if action["action"] == 30:
                add_log(f"Les paramètres sont : {listener.get_all_parameters()}","INFO")

            elif action["action"] == ACTION_CONNEXTION:
                add_log(f"Les points gps sont : {listener.get_all_gps_points()}","INFO")

            else:
                print(f"Action reçue : {action}")
                add_log(f"Action reçue : {action}","UND")
                add_log("Bonjour","INFO")
                add_log("Je teste une injection html <span>j'ai injecté</span>","INFO")
                add_log("Je suis un cgm","CGM")
                add_log("Je suis un warning","WARNING")
                add_log("Moi pas content","ERROR")

                time.sleep(2)

                update_button_permission(action["aircraft_id"],action["action"],False)
        else:
            pass  # print("En attente d'une nouvelle action...")

        time.sleep(0.1)