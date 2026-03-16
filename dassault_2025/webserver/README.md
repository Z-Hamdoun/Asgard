# Section Localisation

Cette partie de l'application web est conçue pour afficher la position de votre drone ainsi que les points de passage (waypoints) prévus pour sa mission sur une carte interactive. Elle vous permet de suivre visuellement et en temps réel la progression du drone par rapport à son itinéraire planifié.

## Fonctionnement Général

Le système repose sur une carte dynamique fournie par la bibliothèque JavaScript Leaflet, qui est mise à jour en continu grâce à une communication en temps réel avec le serveur.

Lorsque vous accédez à la page de localisation (`localisation.html`), le navigateur charge d'abord la structure HTML de base. Ensuite, un script d'initialisation (`static/js/leaflet-init.js`) configure et affiche la carte Leaflet, généralement centrée sur une zone géographique prédéfinie.

Une connexion WebSocket est alors établie entre votre navigateur et le serveur Python via le script `static/js/socket.js`. Cette connexion persistante permet au serveur de pousser des informations vers la page web sans nécessiter de rechargement manuel. Le serveur envoie périodiquement les coordonnées GPS actuelles du drone. Le script `socket.js` reçoit ces données et fait appel aux fonctions définies dans `static/js/maps.js` pour mettre à jour la position du marqueur représentant le drone sur la carte. De même, la liste des waypoints définis pour la mission est transmise et affichée sur la carte par `maps.js`.

## Fichiers Principaux

Plusieurs fichiers collaborent pour assurer le fonctionnement de cette section :

*   **Côté Navigateur (Frontend)** : Le fichier `templates/localisation.html` définit la structure de la page. Les styles visuels sont gérés par `static/css/localisation.css` et `static/css/leaflet.css`. La bibliothèque `static/js/leaflet.js` fournit les fonctionnalités de base de la carte, initialisée par `static/js/leaflet-init.js`. Les fonctions spécifiques à notre application pour manipuler la carte (ajout de marqueurs, etc.) se trouvent dans `static/js/maps.js`. Les interactions utilisateur éventuelles sont gérées par `static/js/script.js`, et la communication temps réel est assurée par `static/js/socket.js`.


## Gestion des Waypoints

Les waypoints représentent les étapes séquentielles d'une mission de vol. Ils sont définis par leurs coordonnées géographiques (latitude, longitude) et potentiellement d'autres informations comme une altitude ou un identifiant. Ces waypoints peuvent être créés soit côté serveur, soit via une interface utilisateur sur la page web si celle-ci a été développée. Toute modification effectuée via l'interface (ajout, suppression, déplacement) est communiquée au serveur via WebSocket pour être enregistrée.
