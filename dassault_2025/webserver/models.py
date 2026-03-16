from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import inspect
import logging

# Initialisation de l'instance SQLAlchemy pour Flask
db = SQLAlchemy()

# Modèle de base de données
class ActionRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    object_id = db.Column(db.Integer, nullable=False)
    action_id = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return f"<ActionRequest {self.id} | Object: {self.object_id} | Action: {self.action_id}>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'object_id': self.object_id,
            'action_id': self.action_id
        }
    
class ActionPermissions(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    object_id = db.Column(db.Integer, nullable=False)  # Nom unique de l'action
    action_id = db.Column(db.Integer, nullable=False)  # Nom unique de l'action
    allowed = db.Column(db.Boolean, default=True)  # True = autorisé, False = bloqué

    def to_dict(self):
        return {
            'id': self.id,
            'object_id': self.object_id,
            'action_id': self.action_id,
            'allowed': self.allowed
        }

# Points composant un chemin
class Parameter(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    object_id = db.Column(db.Integer, nullable=False)  # Nom unique de l'action
    parameter_label = db.Column(db.String, nullable=False)  # Nom unique de l'action
    parameter_value = db.Column(db.String, nullable=False)  # Nom unique de l'action
    updated = db.Column(db.Boolean, default=True)  # True = autorisé, False = bloqué

    def to_dict(self):
        return {
            'id': self.id,
            'object_id': self.object_id,
            'parameter_label': self.parameter_label,
            'parameter_value': self.parameter_value,
            'updated': self.updated
        }

class Marker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    seq = db.Column(db.Integer, nullable=True)
    latitude = db.Column(db.Float(precision=53), nullable=False)  # Utilisation du double (53 bits de précision)
    longitude = db.Column(db.Float(precision=53), nullable=False)  # Utilisation du double (53 bits de précision)
    altitude = db.Column(db.Float(precision=53), nullable=True)  # Utilisation du double (53 bits de précision)
    parameter = db.Column(db.String(20), nullable=False, default="")  # altitude drone, etc.
    marker_type = db.Column(db.String(20), nullable=False, default="waypoint")  # waypoint, target, etc.
    
    def to_dict(self):
        return {
            'id': self.id,
            'seq': self.seq,
            'latitude': str(self.latitude),  # Conversion en string pour la précision
            'longitude': str(self.longitude),  # Conversion en string pour la précision
            'altitude': str(self.altitude),  # Conversion en string pour la précision
            'parameter': self.parameter,
            'marker_type': self.marker_type,
        }
    
class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date_heure = db.Column(db.DateTime, default=datetime.utcnow)
    level = db.Column(db.Text, nullable=False)
    message = db.Column(db.Text, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'date_heure': self.date_heure.strftime('%Y-%m-%d %H:%M:%S'),
            'level': self.level,
            'message': self.message
        }

class UsrPosFollowMe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    altitude = db.Column(db.Float, nullable=True)
    msg = db.Column(db.String(40), nullable=True)
    timestamp = db.Column(db.Float, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'timestamp': self.timestamp
        }

def check_and_sync_database(logger: logging.Logger):
    recreate_required = False

    try:
        inspector = inspect(db.engine)

        # Pour chaque modèle SQLAlchemy connu
        for model_class in db.Model.__subclasses__():
            table_name = model_class.__tablename__
            expected_columns = set(column.name for column in model_class.__table__.columns)

            if not inspector.has_table(table_name):
                logger.warning(f"Table '{table_name}' is missing. Recreating database.")
                recreate_required = True
                break

            existing_columns = set(col['name'] for col in inspector.get_columns(table_name))

            missing = expected_columns - existing_columns
            if missing:
                logger.warning(f"Table '{table_name}' is missing columns: {missing}. Recreating database.")
                recreate_required = True
                break

        if recreate_required:
            db.drop_all()
            db.create_all()
            logger.info("Database tables have been recreated.")
        else:
            db.create_all()  # Crée les tables manquantes, sans supprimer les existantes
            logger.info("Database structure is up to date.")

    except Exception as e:
        logger.warning(f"Error checking database structure: {e}. Creating tables as fallback.")
        db.create_all()