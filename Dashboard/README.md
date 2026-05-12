
# lancer le script

sur la station au sol:
python -m uvicorn app:app --host 0.0.0.0 --port 8000

aller sur 0.0.0.0:8000

checkez l'adresse ip en bas de l'écran

sur Valkyrie et Valhalla:
venv
site {ip en bas de l'écran}

# architecture

À l'éxecution de app.py, la station au sol utilise fastapi pour se comporter comme un Hub centralisé en utilisant websocket pour communiqué avec Valhalla. Dans le même temps, il héberge le website localement.
chaque entité se connecte à une URL spécifique : ws://host/ws/dashboard pour la station au sol et ws://host/ws/Valkyrie pour le Valkyrie. Le server utilise cette connexion se souvenir des noeuds comme un commutateur. Lorsqu'un message arrive, le serveur regarde l'attribut target. S'il s'agit de "Valkyrie", il redirige le JSON vers le tunnel WebSocket correspondant au drone.

Lorsqu'un bouton du site est cliqué, le Dashboard envoie un objet JSON structuré contenant une command et les data associées.

Un intervalle de 1 seconde envoie des messages de type ping pour calculer la latence et vérifier que Valkyrie est toujours en ligne. Le gestionnaire ws.onmessage traite les retours du drone. Il met à jour l'interface en fonction du type de réponse (pong, ack, log, etc.).

Valkyrie exécute un script Python qui agit comme un client persistant.
Le drone utilise asyncio pour écouter les ordres tout en exécutant d'autres tâches en arrière-plan. Pour chaque action, il renvoie un ack ou un message d'erreur (fail) au Dashboard via le serveur central.

L'idée serait d'utiliser websocket 

(valkyrie = helics@valkyrie
valhalla = asgard@valhalla)
