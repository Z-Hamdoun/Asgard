#make a blueprint for the api

from flask import Blueprint, request, jsonify
import time

from logger_utils import logger
from socket_utils import socketio
from models import *
from action import *

bp = Blueprint('api', __name__)

# Route pour envyer automatiquement les modifications de la base de données
@bp.route('/api/db-change', methods=['POST'])
def db_change():
    data = request.get_json()
    socketio.emit('db_change', data)
    return '', 204

# Route pour envoyer les statuts
@bp.route("/api/send_status", methods=["POST"])
def post_status():
    """
    Route API pour recevoir une liste de statuts depuis un client/serveur,
    et la diffuser aux autres clients via SocketIO.
    """
    socketio.emit("update_status", request.json)
    return '', 204

# Route pour ajouter un nouveau marqueur
@bp.route("/api/set_markers", methods=['POST'])
def set_markers():
    """Ajouter un nouveau marqueur"""
    data = request.get_json()

    print(f"set_markers: {data}")

    # suprime les anciens marqueurs
    db.session.query(Marker).delete()
    db.session.commit()

    for marker in data['markers']:

        # Validation des données
        if not all(k in marker for k in ('seq', 'latitude', 'longitude', 'altitude', 'marker_type', 'parameter')):
            db.session.rollback()
            return jsonify({"error": "Données incomplètes"}), 400
    
        # Création du marqueur
        marker = Marker(
            seq=int(marker['seq']),
            latitude=float(marker['latitude']),
            longitude=float(marker['longitude']),
            altitude=float(marker['altitude']),
            parameter=marker['parameter'],
            marker_type=marker['marker_type'],
        )
        
        db.session.add(marker)
    db.session.commit()
    
    return jsonify({"success": True}), 201

# Route pour prendre une action
@bp.route("/api/take_action", methods=["POST"])
def take_action():
    data = request.json
    object_id = data.get("object_id")
    action_id = data.get("action_id")

    if object_id is None or action_id is None:
        return jsonify({"success": False, "error": "Invalid input"}), 400

    # Ajouter la requête dans la base de données
    action = ActionRequest(object_id=object_id, action_id=action_id)
    db.session.add(action)
    db.session.commit()

    action_id = action.id

    # Attente jusqu'à suppression de la requête
    success = False
    for _ in range(30):  # Vérification pendant 3 secondes maximum
        db.session.expire_all()  # Rafraîchir la session SQLAlchemy
        check_action = ActionRequest.query.filter_by(id=action_id).first()
        if check_action is None:
            success = True
            break
        time.sleep(0.1)  # Attendre 1 seconde avant de vérifier à nouveau

    if not success:
        db.session.delete(action)
        db.session.commit()

    return jsonify({"success": success})

# Route pour mettre à jour un paramètre
@bp.route('/api/set_all_parameters', methods=['POST'])
def handle_param_change():
    data = request.json
    
    for new_param in data.get('data'):
        object_id = new_param.get('object_id')
        label = new_param.get('label')
        value = new_param.get('value')

        if object_id is None or label is None or value is None:
            logger.error("Données incomplètes reçues.")
            return

        try:
            # Rechercher un enregistrement existant
            param = Parameter.query.filter_by(object_id=object_id, parameter_label=label).first()

            if param:
                # Mettre à jour l'enregistrement existant
                param.parameter_value = value
                param.updated = True
                logger.info(f"Paramètre mis à jour : object_id={object_id}, label={label}, value={value}")
            else:
                # Insérer un nouvel enregistrement
                new_param = Parameter(
                    object_id=object_id,
                    parameter_label=label,
                    parameter_value=value,
                    updated=True
                )
                db.session.add(new_param)
                logger.info(f"Nouveau paramètre ajouté : object_id={object_id}, label={label}, value={value}")

            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erreur lors de la mise à jour/ajout du paramètre : {e}")
            return jsonify({"error": str(e)}), 400

    return jsonify({"success": True}), 200

# Route pour mettre à jour les coordonnées
@bp.route('/api/set_coordinates', methods=['POST'])
def set_coordinates():
    """Définit manuellement les coordonnées pour un objet"""
    try:

        data = request.json

        # Vérifier si les données sont valide
        try:
            object_id = int(data.get('object_id'))
            latitude = float(data.get('latitude'))
            longitude = float(data.get('longitude'))
            altitude = float(data.get('altitude'))
        except ValueError:
            return jsonify({"error": "Données invalides"}), 400

        socketio.emit('position_update', {
            'object_id': object_id,
            'latitude': latitude,
            'longitude': longitude,
            'altitude': altitude
        })

        return jsonify({"status": "Coordonnées mises à jour avec succès"}), 200
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour des coordonnées: {e}")
        return jsonify({"error": str(e)}), 400
    
# Vide la base de logs
@bp.route('/api/clear_logs', methods=['DELETE'])
def clear_logs():
    db.session.query(Log).delete()
    db.session.commit()
    return jsonify({"message": "Tous les logs ont été supprimés !"}), 200

@bp.route('/api/user_position', methods=['POST'])
def handle_user_position(data):
    """Handle initial user position"""
    
    print("data", data)
    msg = data["msg"]
    print("msg:", msg)
    
    # Get or create the UsrPosFollowMe record
    pos = db.session.query(UsrPosFollowMe).first()
    if not pos:
        pos = UsrPosFollowMe(latitude=0, longitude=0, timestamp=0)
        db.session.add(pos)
        db.session.commit()
    
    if msg == "enable follow me":
        # Reset position when enabling follow me
        pos.latitude = 0
        pos.longitude = 0
        pos.timestamp = time.time()
    elif msg == "ok":
        pos.latitude = data.get("latitude")
        pos.longitude = data.get("longitude")
        pos.timestamp = time.time()
    elif msg == "disable follow me":
        pos.latitude = 0
        pos.longitude = 0
        pos.timestamp = 0
    else:
        print("erreur position utilisateur: ", msg)

    db.session.commit()
    return {'status': 'received'}

@bp.route('/api/update_button_permission', methods=['POST'])
def update_button_permission():
    data = request.json
    object_id = data.get('object_id')
    action_id = data.get('action_id')
    allowed = data.get('allowed')

    if object_id is None or action_id is None or allowed is None:
        return jsonify({"error": "Données invalides"}), 400

    # Vérifier si l'enregistrement existe déjà
    permission = db.session.query(ActionPermissions).filter_by(object_id=object_id, action_id=action_id).first()
    if not permission:
        permission = ActionPermissions(object_id=object_id, action_id=action_id, allowed=allowed)
        db.session.add(permission)
    else:
        permission.allowed = allowed

    db.session.commit()

    socketio.emit('db_change', {
        'operation': 'update',
        'model': 'ActionPermissions',
        'data': [permission.to_dict()]
    })
    return jsonify({"success": True}), 200

@bp.route('/api/add_log', methods=['POST'])
def add_log():
    data = request.json
    message = data.get('message')
    level = data.get('level')

    log = Log(message=message, level=level)
    db.session.add(log)
    db.session.commit()

    socketio.emit('db_change', {
        'operation': 'insert',
        'model': 'Log',
        'data': [log.to_dict()]
    })

    return jsonify({"success": True}), 200

