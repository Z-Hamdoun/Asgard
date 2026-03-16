from flask import request
from flask_socketio import SocketIO, emit

from logger_utils import logger
from models import db

# Créer l'instance SocketIO sans l'initialiser immédiatement
socketio = SocketIO(async_mode='eventlet', cors_allowed_origins="*", logger=False, engineio_logger=False)

@socketio.on('connect')
def handle_connect():
    """Gère la connexion d'un client WebSocket"""
    logger.info(f"Client connecté: {request.sid}")

    # Récupérer toutes les entrées de toutes les tables de la base de données
    all_models = [cls for cls in db.Model.__subclasses__()]
    
    for model in all_models:
        entries = model.query.all()
        data = {
            'operation': 'insert',
            'model': model.__name__,
            'data': [entry.to_dict() for entry in entries]
        }

        # Emmettre les données pour chaque modèle au client connecté
        emit('db_change', data)

@socketio.on('disconnect')
def handle_disconnect(_):
    """Gère la déconnexion d'un client WebSocket"""
    logger.info(f"Client déconnecté: {request.sid}")

@socketio.on_error()
def handle_error(e):
    """Gère les erreurs Socket.IO générales"""
    logger.error(f"Erreur Socket.IO: {str(e)}")

def init_socketio(app):
    # Initialiser socketio avec l'application Flask
    socketio.init_app(app)