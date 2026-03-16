// Define STATIC_URL if not already defined
if (typeof STATIC_URL === 'undefined') {
    var STATIC_URL = '/static/';
}

// Global variables for FollowMe functionality
let FollowMeEnabled = false;
let watchId = null;

// Global function for FollowMe toggle
function scriptToggleFollowMe() {
    FollowMeEnabled = !FollowMeEnabled;
    
    if (FollowMeEnabled) {
        console.log('FollowMe enabled');
        if (navigator.geolocation) {
            socket.emit('user_position', {
                latitude: 0,
                longitude: 0,
                altitude: 0,
                msg: "enable follow me",
                timestamp: new Date().toISOString()
            });
            watchId = navigator.geolocation.watchPosition(updateLocation, handleLocationError, {
                enableHighAccuracy: true, // Prioritize GPS accuracy
                maximumAge: 0,           // Always fetch fresh location data
            });
            if (document.getElementById('toggle-followme')) {
                document.getElementById('toggle-followme').textContent = 'Désactiver le follow me';
            }
        } else {
            alert("Geolocation is not supported by your browser.");
            FollowMeEnabled = false;
        }
    } else {
        console.log('FollowMe disabled');
        if (watchId !== null) {
            navigator.geolocation.clearWatch(watchId);
            watchId = null;
        }
        socket.emit('user_position', {
            latitude: 0,
            longitude: 0,
            altitude: 0,
            msg: "disable follow me",
            timestamp: new Date().toISOString()
        });
        if (document.getElementById('toggle-followme')) {
            document.getElementById('toggle-followme').textContent = 'Activer le follow me';
        }
    }
}

// Global function for location updates
function updateLocation(position) {
    const userLat = position.coords.latitude;
    const userLon = position.coords.longitude;
    const userAlt = position.coords.altitude;

    socket.emit('user_position', {
        latitude: userLat,
        longitude: userLon,
        altitude: userAlt,
        msg: "ok",
        timestamp: new Date().toISOString()
    });

    console.log(`Live Coordinates: Latitude: ${userLat}, Longitude: ${userLon}, Altitude: ${userAlt}`);
}

// Global function for location errors
function handleLocationError(error) {
    if (FollowMeEnabled) {
        scriptToggleFollowMe();  // Call the function to disable FollowMe
    }
    let errorMessage = '';
    switch (error.code) {
        case error.PERMISSION_DENIED:
            errorMessage = "Location permission denied by the user.";
            break;
        case error.POSITION_UNAVAILABLE:
            errorMessage = "Location information is unavailable.";
            break;
        case error.TIMEOUT:
            errorMessage = "Location request timed out.";
            break;
        default:
            errorMessage = "An unknown error occurred.";
            break;
    }
    console.error("Error getting location: ", errorMessage);
    socket.emit('user_position', {
        latitude: 0,
        longitude: 0,
        altitude: 0,
        msg: errorMessage,
        timestamp: new Date().toISOString()
    });
    alert(errorMessage);
}

// Ensure Leaflet is loaded properly
if (typeof L === 'undefined' || typeof L.map !== 'function') {
    console.error("Leaflet library is not loaded correctly.");
    // Halt further script execution
} else {
    //Ajout d'icon custom
    const droneIcon = L.icon({
        iconUrl: STATIC_URL + 'images/droneImage.png',  // Path to the drone icon
        iconSize: [32, 32],  // Size of the icon
        iconAnchor: [16, 16],  // Anchor point (center the icon)
        popupAnchor: [0, -16]  // Position of the popup relative to the icon
    });
    const planeIcon = L.icon({
        iconUrl: STATIC_URL + 'images/planeImage.png',  // Path to the plane icon
        iconSize: [16, 16],  // Size of the icon
        iconAnchor: [8, 8],  // Anchor point (center the icon)
        popupAnchor: [0, -16]  // Position of the popup relative to the icon
    });

    const gcsIcon = L.icon({
        iconUrl: STATIC_URL + 'images/gcsImage.png',  // Path to the gcs icon
        iconSize: [32, 32],  // Size of the icon
        iconAnchor: [16, 16],  // Anchor point (center the icon)
        popupAnchor: [0, -16]  // Position of the popup relative to the icon
    });

    const targetIcon = L.icon({
        iconUrl: STATIC_URL + 'images/targetImage.jpg',  // Path to the target icon
        iconSize: [32, 32],  // Size of the icon
        iconAnchor: [16, 16],  // Anchor point (center the icon)
        popupAnchor: [0, -16]  // Position of the popup relative to the icon
    });

    // Initialize the map
    // Check that the map container exists before initializing the map
    const mapContainer = document.getElementById('map');
    if (!mapContainer) {
        console.error("Map container not found!");
    } else {
        // Remove existing map validation and always create a new instance
        const map = L.map('map').setView([48.7, 2.176666], 13);
        window.map = map;        // Add tiles from our local cache or Google Maps
        L.tileLayer('/tiles/{z}/{x}/{y}.png', {
            maxZoom: 20,
            errorTileUrl: STATIC_URL + 'images/error-tile.png',  // Fallback image for missing tiles
            updateWhenIdle: false
        }).addTo(map);

        // Wait for the map to be fully loaded before proceeding.
        map.whenReady(function() {
            console.log("Map is fully loaded.");
            let marker; 
            let droneMarker, planeMarker;
            let userLat;
            let userLon;

            // Au debut on centre sur la geolocalisation de l'user


            // Pour recentrer la map + en dessous il y a un listener qui chope le click et le garde pour lui, sinon ca compte aussi pour un click sur la map et ca pose un pin
            function recenterMap() {
                // Center map to drone's location
                //find a way to get the drone location :
                var lat = 0;
                var lon = 0;
                const latElement = document.getElementById(`drone-latitude`);
                console.log("latElement", latElement)
                if (latElement) {
                    lat = latElement.textContent;
                }
                
                // Update longitude
                const lngElement = document.getElementById(`drone-longitude`);
                if (lngElement) {
                    lon = lngElement.textContent;
                }


                //map.setView(new L.LatLng(userLat, userLon), 13);
                map.setView(new L.LatLng(lat, lon), 17);
                console.log("recenter")
            };

            document.getElementById('recenter-button').addEventListener('click', function(event) {
                event.stopPropagation();  // Stop the click from propagating to the map
                recenterMap();            // Call the recenterMap function
            });

            // CHECK GPS
            function isValidCoordinate(lat, lon) {
                const latitude = parseFloat(lat);
                const longitude = parseFloat(lon);
                return (
                    !isNaN(latitude) && latitude >= -90 && latitude <= 90 &&
                    !isNaN(longitude) && longitude >= -180 && longitude <= 180
                );
            }

            // Gestion des clics sur la carte - Modifié pour vérifier le mode marqueur
            // Le gestionnaire de clics est déplacé vers maps.js pour gérer le mode marqueur
            // On ne définit pas de gestionnaire ici pour éviter les conflits avec maps.js
            // L'ancien code est conservé en commentaire ci-dessous pour référence
            
            // Position updates handling
            socket.on('position_update', function(positions) {
                try {
                    updatePosition(positions);
                }
                catch (error) {
                    console.error('Error handling position update:', error);
                }
            });

            // METS A JOURS LES MARQUEURS D'AVION/DRONE
            function updatePosition(data) {
                // check if data.drone exists :
                if (data.drone) {
                    dataDrone = data.drone;
                    // Update drone coordinates
                    document.getElementById('drone-latitude').innerText = (Number(dataDrone.latitude) || 0).toFixed(6);
                    document.getElementById('drone-longitude').innerText = (Number(dataDrone.longitude) || 0).toFixed(6);
                    document.getElementById('drone-altitude').innerText = dataDrone.altitude;

                    // Update or create the drone marker
                    if (droneMarker) {
                        droneMarker.setLatLng([dataDrone.latitude, dataDrone.longitude])
                                .bindPopup(`Drone Location: Altitude ${dataDrone.altitude}m`);
                    } else {
                        droneMarker = L.marker([dataDrone.latitude, dataDrone.longitude], { icon: droneIcon })
                                    .addTo(map)
                                    .bindPopup(`Drone Location: Altitude ${dataDrone.altitude}m`);
                    }
                }
                // check if data.avion exists :
                if (data.avion) {
                    dataPlane = data.avion;
                    // Update plane coordinates
                    document.getElementById('plane-latitude').innerText = dataPlane.latitude.toFixed(6);
                    document.getElementById('plane-longitude').innerText = dataPlane.longitude.toFixed(6);
                    document.getElementById('plane-altitude').innerText = dataPlane.altitude;
                    
                    // Update or create the plane marker
                    if (planeMarker) {
                        planeMarker.setLatLng([dataPlane.latitude, dataPlane.longitude])
                                .bindPopup(`Plane Location: Altitude ${dataPlane.altitude}m`);
                    } else {
                        planeMarker = L.marker([dataPlane.latitude, dataPlane.longitude], { icon: planeIcon })
                                    .addTo(map)
                                    .bindPopup(`Plane Location: Altitude ${dataPlane.altitude}m`);
                    }
                }
            }
        });
    }
}

// Fonction globale pour afficher une notification
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.classList.add('show');
    }, 10);
    
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, 3000);
}

// Exposer les fonctions globales
window.showNotification = showNotification;
