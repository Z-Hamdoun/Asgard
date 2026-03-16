// maps.js - Gestion des marqueurs et des chemins sur la carte interactive

document.addEventListener('DOMContentLoaded', function() {
    // Vérifier que nous sommes sur la page de localisation
    if (!document.getElementById('map')) {
        return;
    }    // Définir l'URL de base pour les ressources statiques
    const STATIC_URL = '/static/';
    
    // Configurer le chemin des icônes Leaflet AVANT toute utilisation
    L.Icon.Default.imagePath = STATIC_URL + 'images/';

    // Variables globales pour stocker les couches Leaflet
    window.mapLayers = {
        markers: L.layerGroup(),
        paths: L.layerGroup()
    };

    // État de l'application
    const appState = {
        markerMode: false,
        pathMode: false,
        currentPath: [],
        pathPointsCount: 0,
        mapInitialized: false // Nouveau drapeau pour suivre l'initialisation
    };

    // Référence aux éléments DOM
    const toggleMarkerModeBtn = document.getElementById('toggle-marker-mode');
    const viewFilterSelect = document.getElementById('view-filter');
    const resetButton = document.getElementById('reset-button');
    let markerList = document.getElementById('marker-list');
    let pathList = document.getElementById('path-list');
    const markerModal = document.getElementById('marker-modal');
    const pathModal = document.getElementById('path-modal');
    const markerForm = document.getElementById('marker-form');
    const pathForm = document.getElementById('path-form');

    // Configuration des onglets
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanels = document.querySelectorAll('.tab-panel');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            // Retirer la classe active de tous les boutons
            tabBtns.forEach(b => b.classList.remove('active'));
            // Ajouter la classe active au bouton cliqué
            this.classList.add('active');
            
            // Cacher tous les panneaux
            tabPanels.forEach(panel => panel.classList.remove('active'));
            // Afficher le panneau correspondant
            const tabId = this.getAttribute('data-tab');
            document.getElementById(tabId).classList.add('active');
        });
    });

    // Gestionnaires de fermeture des modals
    document.querySelectorAll('.close').forEach(closeBtn => {
        closeBtn.addEventListener('click', function() {
            markerModal.style.display = 'none';
            pathModal.style.display = 'none';
        });
    });

    // Fermer les modals en cliquant en dehors
    window.addEventListener('click', function(event) {
        if (event.target === markerModal) {
            markerModal.style.display = 'none';
        }
        if (event.target === pathModal) {
            pathModal.style.display = 'none';
        }
    });    // Définir l'icône de marqueur par défaut avec le bon chemin
    const defaultMarkerIcon = L.icon({
        iconUrl: STATIC_URL + 'images/marker-icon.png',
        iconSize: [25, 41],
        iconAnchor: [12, 41],
        popupAnchor: [0, -41],
        shadowUrl: STATIC_URL + 'images/marker-shadow.png',
        shadowSize: [41, 41],
        shadowAnchor: [12, 41]
    });

    // Gestion du mode marqueur
    if (toggleMarkerModeBtn) {
        toggleMarkerModeBtn.addEventListener('click', function() {
            appState.markerMode = !appState.markerMode;
            this.classList.toggle('active');
            
            if (appState.markerMode) {
                this.textContent = 'Annuler Marqueur';
                window.showNotification('Mode marqueur activé. Cliquez sur la carte pour placer un marqueur.', 'info');
            } else {
                this.textContent = 'Placer Marqueur';
                window.showNotification('Mode marqueur désactivé', 'info');
            }
        });
    }

    // Gestionnaire de clic sur la carte - pour ajouter des marqueurs ou points de chemin
    function setupMapClickHandler() {
        if (typeof window.map === 'undefined') {
            console.error('La carte n\'est pas disponible. Veuillez charger script.js en premier.');
            return;
        }

        window.map.on('click', function(event) {
            const { lat, lng } = event.latlng;
            
            // Ajout d'une logique pour gérer les marqueurs de départ, d'arrivée et de cible
            if (appState.markerMode) {
                // Ouvrir la modal pour ajouter un marqueur
                document.getElementById('marker-lat').value = lat.toFixed(6);
                document.getElementById('marker-lng').value = lng.toFixed(6);
                markerModal.style.display = 'block';

                // Ajouter un gestionnaire pour le formulaire de marqueur
                markerForm.addEventListener('submit', function handleMarkerSubmit(event) {
                    event.preventDefault();

                    const markerType = document.getElementById('marker-type').value;
                    const markerData = {
                        latitude: lat,
                        longitude: lng,
                        type: markerType
                    };

                    // Ajouter le marqueur à la carte
                    let icon;
                    switch (markerType) {
                        case 'start':
                            icon = L.icon({
                                iconUrl: STATIC_URL + 'images/marker-icon.png',
                                iconSize: [26, 40],
                                iconAnchor: [16, 16],
                                popupAnchor: [0, -16]
                            });
                            break;
                        case 'end':
                            icon = L.icon({
                                iconUrl: STATIC_URL + 'images/marker-icon.png',
                                iconSize: [26, 40],
                                iconAnchor: [16, 16],
                                popupAnchor: [0, -16]
                            });
                            break;
                        case 'target':
                        default:
                            icon = defaultMarkerIcon;
                    }

                    const marker = L.marker([lat, lng], { icon }).addTo(window.map);
                    window.mapLayers.markers.addLayer(marker);

                    // Ajouter le marqueur à la liste des chemins si nécessaire
                    appState.currentPath.push({ latitude: lat, longitude: lng });

                    // Tracer automatiquement les chemins si au moins deux points sont présents
                    if (appState.currentPath.length > 1) {
                        const lastPoint = appState.currentPath[appState.currentPath.length - 2];
                        const currentPoint = appState.currentPath[appState.currentPath.length - 1];
                        const line = L.polyline([
                            [lastPoint.latitude, lastPoint.longitude],
                            [currentPoint.latitude, currentPoint.longitude]
                        ], {
                            color: '#ff7800',
                            weight: 3,
                            opacity: 0.5
                        }).addTo(window.map);
                        window.mapLayers.paths.addLayer(line);
                    }

                    // Réinitialiser le formulaire et fermer la modal
                    markerForm.reset();
                    markerModal.style.display = 'none';

                    // Supprimer le gestionnaire pour éviter les doublons
                    markerForm.removeEventListener('submit', handleMarkerSubmit);
                });
            } else if (appState.pathMode) {
                // Ajouter un point au chemin actuel
                appState.currentPath.push({
                    latitude: lat,
                    longitude: lng,
                    altitude: 0,
                    order: appState.pathPointsCount++
                });
                
                // Dessiner le point sur la carte
                const marker = L.circleMarker([lat, lng], {
                    radius: 5,
                    fillColor: '#ff7800',
                    color: '#000',
                    weight: 1,
                    opacity: 1,
                    fillOpacity: 0.8
                }).addTo(window.map);
                
                // Si c'est au moins le deuxième point, dessiner une ligne
                if (appState.currentPath.length > 1) {
                    const lastPoint = appState.currentPath[appState.currentPath.length - 2];
                    const line = L.polyline([
                        [lastPoint.latitude, lastPoint.longitude],
                        [lat, lng]
                    ], {
                        color: '#ff7800',
                        weight: 3,
                        opacity: 0.5,
                        dashArray: '5, 10'
                    }).addTo(window.map);
                }
                
                if (appState.currentPath.length > 1) {
                    pathModal.style.display = 'block';
                    document.getElementById('path-points').value = JSON.stringify(appState.currentPath);
                }
            }
        });
    }

    // Charger les marqueurs depuis le serveur
    function loadMarkers() {
        // Afficher un indicateur de chargement
        console.log('Chargement des marqueurs...');
        
        // Vérifier que l'élément markerList existe
        if (!markerList) {
            console.error('Élément markerList non trouvé!');
            markerList = document.getElementById('marker-list');
            if (!markerList) {
                console.error('Impossible de trouver l\'élément marker-list dans le DOM');
                return;
            }
        }
        
        // Créer un wrapper UL si nécessaire pour l'accessibilité
        let markersUl = markerList.querySelector('ul');
        if (!markersUl) {
            markersUl = document.createElement('ul');
            markersUl.className = 'markers-ul';
            markersUl.style.listStyle = 'none';
            markersUl.style.padding = '0';
            markersUl.style.margin = '0';
            markerList.appendChild(markersUl);
        } else {
            // Vider la liste existante
            while (markersUl.firstChild) {
                markersUl.removeChild(markersUl.firstChild);
            }
        }
        
        fetch('/api/markers')
        .then(response => {
            if (!response.ok) {
                throw new Error('Erreur réseau lors du chargement des marqueurs');
            }
            return response.json();
        })
        .then(markers => {
            console.log('Marqueurs reçus:', markers);
            
            // Vider le groupe de couches de marqueurs
            window.mapLayers.markers.clearLayers();
            
            if (markers.length === 0) {
                // Afficher un message si aucun marqueur dans une liste pour accessibilité
                const emptyLi = document.createElement('li');
                emptyLi.className = 'info-message';
                emptyLi.textContent = 'Aucun marqueur enregistré';
                markersUl.appendChild(emptyLi);
            } else {
                console.log(`Création de ${markers.length} éléments marqueur dans la liste...`);
                
                // Utiliser un fragment de document pour optimiser les performances
                const fragment = document.createDocumentFragment();
                
                markers.forEach((marker, index) => {
                    // Créer l'icône en fonction du type
                    let icon;
                    switch(marker.marker_type) {
                        case 'target':
                            icon = L.icon({
                                iconUrl: STATIC_URL + 'images/targetImage.jpg',
                                iconSize: [32, 32],
                                iconAnchor: [16, 16],
                                popupAnchor: [0, -16]
                            });
                            break;
                        case 'start':
                            icon = L.icon({
                                iconUrl: STATIC_URL + 'images/marker-icon.png',
                                iconSize: [32, 32],
                                iconAnchor: [16, 16],
                                popupAnchor: [0, -16]
                            });
                            break;
                        case 'end':
                            icon = L.icon({
                                iconUrl: STATIC_URL + 'images/marker-icon.png',
                                iconSize: [32, 32],
                                iconAnchor: [16, 16],
                                popupAnchor: [0, -16]
                            });
                            break;
                        default:
                            icon = defaultMarkerIcon;
                    }
                    
                    // Vérifier que les coordonnées sont valides
                    if (!isNaN(parseFloat(marker.latitude)) && !isNaN(parseFloat(marker.longitude))) {
                        const latitude = parseFloat(marker.latitude).toFixed(6);
                        const longitude = parseFloat(marker.longitude).toFixed(6);

                        // Ajouter le marqueur à la carte
                        const markerLayer = L.marker([latitude, longitude], {
                            icon: icon,
                            objectId: marker.object_id
                        }).bindPopup(`
                            <h3>${marker.name || 'Marqueur sans nom'}</h3>
                            <p>${marker.description || ''}</p>
                            <p>Lat: ${latitude}</p>
                            <p>Lng: ${longitude}</p>
                            <p>Alt: ${marker.altitude} m</p>
                        `);
                        
                        window.mapLayers.markers.addLayer(markerLayer);
                    } else {
                        console.error('Coordonnées invalides pour le marqueur:', marker);
                    }
                    
                    // Ajouter à la liste HTML avec un LI approprié pour l'accessibilité
                    const markerLi = document.createElement('li');
                    markerLi.className = 'marker-item';
                    markerLi.style.display = 'flex'; // Forcer l'affichage
                    
                    const markerSpan = document.createElement('span');
                    markerSpan.textContent = `${marker.name || 'Marqueur sans nom'} (${marker.object_id === 1 ? 'Drone' : 'Avion'})`;
                    markerLi.appendChild(markerSpan);
                    
                    const deleteBtn = document.createElement('button');
                    deleteBtn.className = 'delete-marker';
                    deleteBtn.setAttribute('data-id', marker.id);
                    deleteBtn.setAttribute('aria-label', `Supprimer le marqueur ${marker.name || 'sans nom'}`);
                    deleteBtn.textContent = '×';
                    markerLi.appendChild(deleteBtn);
                    
                    fragment.appendChild(markerLi);
                    console.log(`Ajout du marqueur ${index} (${marker.name || 'sans nom'}) à la liste`);
                });
                
                // Ajouter tous les éléments en une seule opération
                markersUl.appendChild(fragment);
                
                // Forcer un reflow du DOM
                markerList.style.display = 'none';
                markerList.offsetHeight; // Force reflow
                markerList.style.display = '';
            }
            
            // Ajouter le groupe de marqueurs à la carte si elle est disponible
            if (window.map) {
                window.mapLayers.markers.addTo(window.map);
            }
            
            // Ajouter les gestionnaires d'événements pour supprimer des marqueurs
            document.querySelectorAll('.delete-marker').forEach(button => {
                button.addEventListener('click', function() {
                    const markerId = this.getAttribute('data-id');
                    
                    if (confirm('Êtes-vous sûr de vouloir supprimer ce marqueur?')) {
                        fetch(`/api/markers/${markerId}`, { method: 'DELETE' })
                        .then(response => {
                            if (!response.ok) {
                                throw new Error('Erreur réseau lors de la suppression du marqueur');
                            }
                            return response.json();
                        })
                        .then(data => {
                            window.showNotification('Marqueur supprimé', 'success');
                            // Supprimer les marqueurs ET les chemins associés
                            refreshMarkerList();
                            // Rafraîchir les chemins pour effacer les segments menant au marqueur supprimé
                            refreshPathList();
                            // Nettoyer les lignes qui pourraient encore être présentes
                            clearOrphanedLines();
                        })
                        .catch(error => {
                            console.error('Erreur lors de la suppression du marqueur:', error);
                            window.showNotification('Erreur lors de la suppression: ' + error.message, 'error');
                        });
                    }
                });
            });
            
            // Notification pour confirmer le chargement
            console.log('Liste des marqueurs mise à jour avec succès');
        })
        .catch(error => {
            console.error('Erreur lors du chargement des marqueurs:', error);
            markerList.innerHTML = `<div class="error-message">Erreur: ${error.message}</div>`;
            window.showNotification('Erreur lors du chargement des marqueurs: ' + error.message, 'error');
        });
    }

    // Ajouter ces fonctions pour forcer un rafraîchissement des listes
    function refreshMarkerList() {
        console.log('Forçage du rafraîchissement de la liste des marqueurs');
        if (markerList) {
            // Forcer un reflow du DOM
            markerList.style.display = 'none';
            markerList.offsetHeight; // Force reflow
            markerList.style.display = '';
        }
        loadMarkers();
    }

    // Gestionnaire d'envoi du formulaire de marqueur
    markerForm.addEventListener('submit', function(event) {
        event.preventDefault();

        // Vérifier que marker-alt-larg-avion et marker-alt-larg-drone sont des nombres
        const altLargAvion = parseInt(document.getElementById('marker-alt-larg-avion').value);
        const altLargDrone = parseInt(document.getElementById('marker-alt-larg-drone').value);
        if (isNaN(altLargAvion) || isNaN(altLargDrone)) {
            window.showNotification('Erreur: Les valeurs d\'altitude doivent être des nombres valides', 'error');
            return;
        }
        const markerData = {
            marker_type: document.getElementById('marker-type').value,
            latitude: parseFloat(document.getElementById('marker-lat').value),
            longitude: parseFloat(document.getElementById('marker-lng').value),
            object_id: parseInt(document.getElementById('marker-object').value),
            alt_larg_avion: parseFloat(document.getElementById('marker-alt-larg-avion').value),
            alt_larg_drone: parseInt(document.getElementById('marker-alt-larg-drone').value)
        };
        
        // Afficher un indicateur de chargement
        window.showNotification('Ajout du marqueur en cours...', 'info');
        
        // Envoyer au serveur
        fetch('/api/markers', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(markerData)
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Erreur réseau lors de l\'ajout du marqueur');
            }
            return response.json();
        })
        .then(data => {
            window.showNotification('Marqueur ajouté avec succès', 'success');
            markerModal.style.display = 'none';
            
            // Réinitialiser le formulaire
            markerForm.reset();
            
            // Forcer le rafraîchissement
            refreshMarkerList();
        })
        .catch(error => {
            console.error('Erreur lors de l\'ajout du marqueur:', error);
            window.showNotification('Erreur lors de l\'ajout du marqueur: ' + error.message, 'error');
        });
    });

    // Gestionnaire d'envoi du formulaire de chemin
    pathForm.addEventListener('submit', function(event) {
        event.preventDefault();
        
        const objectId = parseInt(document.getElementById('path-object').value);
        
        // Vérifier si tous les points appartiennent au même objet (drone ou avion)
        let allPointsSameObject = true;
        let pointsWithMarkers = [];
        
        // Récupérer les marqueurs existants pour les comparer avec les points du chemin
        fetch('/api/markers')
        .then(response => response.json())
        .then(markers => {
            // Pour chaque point du chemin, vérifier s'il existe un marqueur correspondant
            appState.currentPath.forEach(point => {
                // Rechercher les marqueurs proches du point (avec une tolérance)
                const tolerance = 0.00001; // Environ 1m de tolérance
                const nearbyMarkers = markers.filter(marker => 
                    Math.abs(marker.latitude - point.latitude) < tolerance && 
                    Math.abs(marker.longitude - point.longitude) < tolerance
                );
                
                // Si des marqueurs sont trouvés près du point, vérifier leur objet_id
                if (nearbyMarkers.length > 0) {
                    const matchingMarker = nearbyMarkers[0]; // Prendre le premier marqueur correspondant
                    pointsWithMarkers.push({
                        point: point,
                        marker: matchingMarker
                    });
                    
                    // Si l'objet_id du marqueur ne correspond pas à l'objet sélectionné
                    if (matchingMarker.object_id !== objectId) {
                        allPointsSameObject = false;
                    }
                }
            });
            
            // Si tous les points n'appartiennent pas au même objet, afficher un message d'erreur
            if (!allPointsSameObject) {
                window.showNotification('Erreur: Un chemin ne peut pas contenir des points appartenant à la fois au drone et à l\'avion', 'error');
                return;
            }
            
            // Si tout est ok, continuer avec l'ajout du chemin
            const pathData = {
                name: document.getElementById('path-name').value || 'Chemin sans nom',
                object_id: objectId,
                color: document.getElementById('path-color').value,
                points: appState.currentPath
            };
            
            // Afficher un indicateur de chargement
            window.showNotification('Ajout du chemin en cours...', 'info');
            
            // Envoyer au serveur
            fetch('/api/paths', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(pathData)
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Erreur réseau lors de l\'ajout du chemin');
                }
                return response.json();
            })
            .then(data => {
                window.showNotification('Chemin ajouté avec succès', 'success');
                pathModal.style.display = 'none';
                
                // Réinitialiser le chemin actuel
                appState.currentPath = [];
                appState.pathPointsCount = 0;
                
                // Réinitialiser le formulaire
                pathForm.reset();
                
                // Forcer le rafraîchissement
                refreshPathList();
                
                // Supprimer les points et lignes temporaires
                window.map.eachLayer(function(layer) {
                    if (layer instanceof L.CircleMarker || 
                       (layer instanceof L.Polyline && layer.options.dashArray === '5, 10')) {
                        window.map.removeLayer(layer);
                    }
                });
            })
            .catch(error => {
                console.error('Erreur lors de l\'ajout du chemin:', error);
                window.showNotification('Erreur lors de l\'ajout du chemin: ' + error.message, 'error');
            });
        })
        .catch(error => {
            console.error('Erreur lors de la vérification des marqueurs:', error);
            window.showNotification('Erreur lors de la validation du chemin: ' + error.message, 'error');
        });
    });

    // Réinitialiser les marqueurs et chemins
    resetButton.addEventListener('click', function() {
        if (confirm('Êtes-vous sûr de vouloir supprimer tous les marqueurs et chemins?')) {
            // Afficher un indicateur de chargement
            window.showNotification('Suppression en cours...', 'info');
            
            // Supprimer tous les marqueurs
            fetch('/api/markers/reset', { method: 'DELETE' })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Erreur réseau lors de la suppression des marqueurs');
                }
                return response.json();
            })
            .then(data => {
                console.log('Marqueurs supprimés:', data);
                refreshMarkerList();
            })
            .catch(error => {
                console.error('Erreur lors de la suppression des marqueurs:', error);
                window.showNotification('Erreur: ' + error.message, 'error');
            });
            
            // Supprimer tous les chemins
            fetch('/api/paths/reset', { method: 'DELETE' })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Erreur réseau lors de la suppression des chemins');
                }
                return response.json();
            })
            .then(data => {
                console.log('Chemins supprimés:', data);
                refreshPathList();
            })
            .catch(error => {
                console.error('Erreur lors de la suppression des chemins:', error);
                window.showNotification('Erreur: ' + error.message, 'error');
            });
            
            window.showNotification('Tous les marqueurs et chemins ont été supprimés', 'info');
        }
    });

    // Filtrer la vue des objets
    viewFilterSelect.addEventListener('change', function() {
        const value = this.value;
        filterMapObjects(value);
    });

    function filterMapObjects(filter) {
        // Réinitialiser d'abord
        window.mapLayers.markers.eachLayer(layer => {
            layer.addTo(window.map);
        });
        
        if (filter === 'all') return;
        
        // Filtrer les marqueurs
        window.mapLayers.markers.eachLayer(layer => {
            if (layer.options.objectId !== undefined) {
                const objectId = layer.options.objectId;
                const objectType = objectId === 1 ? 'drone' : 'plane';
                
                if (filter !== objectType) {
                    window.map.removeLayer(layer);
                }
            }
        });
    }

    // Initialiser les fonctionnalités de la carte
    function initMapFeatures() {
        console.log('Initialisation des fonctionnalités de carte...');
        
        // Vérifier que la carte est bien initialisée
        if (typeof window.map === 'undefined') {
            console.error('La carte n\'est pas disponible. Réessai dans 500ms...');
            setTimeout(initMapFeatures, 500);
            return;
        }
        
        // Marquer comme initialisé
        appState.mapInitialized = true;
        
        // Ajouter les couches à la carte
        window.mapLayers.markers.addTo(window.map);
        window.mapLayers.paths.addTo(window.map);
        
        // Configurer le gestionnaire de clics sur la carte
        setupMapClickHandler();
        
        // Restaurer les chemins sauvegardés dans localStorage (si existant)
        restorePathsFromLocalStorage();
        
        // Charger les marqueurs et chemins
        loadMarkers();
        loadPaths();
        
        console.log('Carte complètement initialisée');
    }
    
    // Fonction pour restaurer les chemins depuis localStorage après un refresh
    function restorePathsFromLocalStorage() {
        try {
            const savedPaths = JSON.parse(localStorage.getItem('savedPaths') || '[]');
            if (savedPaths.length > 0) {
                console.log(`Restauration de ${savedPaths.length} chemins depuis localStorage`);
                
                // Nettoyer les chemins restaurés du localStorage pour éviter les duplications
                fetch('/api/paths')
                .then(response => response.json())
                .then(serverPaths => {
                    // Récupérer seulement les IDs de chemins sur le serveur
                    const serverPathIds = serverPaths.map(path => path.id);
                    
                    // Filtrer les chemins sauvegardés pour ne garder que ceux qui existent sur le serveur
                    const validPaths = savedPaths.filter(path => serverPathIds.includes(path.id));
                    
                    // Mettre à jour le localStorage avec les chemins valides
                    localStorage.setItem('savedPaths', JSON.stringify(validPaths));
                    
                    // Afficher chaque chemin valide sur la carte
                    validPaths.forEach(path => {
                        if (path.points && path.points.length > 1) {
                            // Créer une polyline pour chaque chemin sauvegardé
                            const pathLayer = L.polyline(path.points, {
                                color: path.color || '#3388ff',
                                weight: 3,
                                objectId: path.objectId,
                                pathId: path.id,
                                restored: true // Marquer comme restauré
                            }).bindPopup(`<h3>${path.name || 'Chemin restauré'}</h3>`);
                            
                            // Ajouter temporairement le chemin à la carte
                            window.mapLayers.paths.addLayer(pathLayer);
                        }
                    });
                })
                .catch(error => {
                    console.error('Erreur lors de la validation des chemins sauvegardés:', error);
                });
            }
        } catch (e) {
            console.error('Erreur lors de la restauration des chemins depuis localStorage:', e);
            // En cas d'erreur, nettoyer le localStorage pour éviter des problèmes futurs
            localStorage.removeItem('savedPaths');
        }
    }

    // Vérifier si la carte est déjà disponible
    if (typeof window.map !== 'undefined') {
        console.log('Carte déjà disponible, initialisation immédiate');
        initMapFeatures();
    } else {
        console.log('Attente de l\'initialisation de la carte...');
        // Vérifier régulièrement si la carte est disponible
        const checkMapInterval = setInterval(function() {
            if (typeof window.map !== 'undefined') {
                clearInterval(checkMapInterval);
                console.log('Carte détectée, initialisation');
                initMapFeatures();
            }
        }, 100); // Vérifier toutes les 100ms
        
        // Arrêter la vérification après 10 secondes pour éviter une boucle infinie
        setTimeout(function() {
            clearInterval(checkMapInterval);
            if (!appState.mapInitialized) {
                console.error('Impossible d\'initialiser la carte après 10 secondes');
                window.showNotification('Erreur: La carte n\'a pas pu être initialisée', 'error');
            }
        }, 10000);
    }
});

// Si on utilise la fonction showNotification dans ce script
if (typeof window.showNotification !== 'function') {
    window.showNotification = function(message, type) {
        console.log(`Notification (${type}): ${message}`);
        
        // Créer l'élément de notification s'il n'existe pas
        let notificationContainer = document.getElementById('notification-container');
        if (!notificationContainer) {
            notificationContainer = document.createElement('div');
            notificationContainer.id = 'notification-container';
            notificationContainer.style.position = 'fixed';
            notificationContainer.style.top = '20px';
            notificationContainer.style.right = '20px';
            notificationContainer.style.zIndex = '9999';
            document.body.appendChild(notificationContainer);
        }
        
        // Créer la notification
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        notification.style.padding = '10px 15px';
        notification.style.marginBottom = '10px';
        notification.style.borderRadius = '4px';
        notification.style.color = '#fff';
        notification.style.boxShadow = '0 2px 4px rgba(0,0,0,0.2)';
        notification.style.transition = 'all 0.3s ease';
        
        // Styles spécifiques par type
        switch (type) {
            case 'success':
                notification.style.backgroundColor = '#4CAF50';
                break;
            case 'error':
                notification.style.backgroundColor = '#f44336';
                break;
            case 'info':
            default:
                notification.style.backgroundColor = '#2196F3';
        }
        
        // Ajouter la notification
        notificationContainer.appendChild(notification);
        
        // Supprimer après 3 secondes
        setTimeout(function() {
            notification.style.opacity = '0';
            setTimeout(function() {
                notificationContainer.removeChild(notification);
            }, 300);
        }, 3000);
    };
}
