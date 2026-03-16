import logging

# disable logging
logging.getLogger('werkzeug').setLevel(logging.ERROR)  # Désactiver les logs de Werkzeug
logging.basicConfig(level=logging.CRITICAL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('olympe')
logger.setLevel(logging.INFO)