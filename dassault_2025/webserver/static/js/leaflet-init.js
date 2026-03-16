// Initialisation spécifique de Leaflet

// Vérifier si Leaflet est chargé
if (typeof L === 'undefined') {
    console.error('Leaflet n\'est pas chargé correctement!');
} else {
    console.log('Leaflet est prêt à être utilisé');
}

// Configurer Leaflet pour les besoins spécifiques
if (typeof L !== 'undefined') {
    // S'assurer que les popups se ferment lorsqu'on clique sur la carte
    L.Map.mergeOptions({
        closePopupOnClick: true
    });
    
    // Ajouter une méthode pour calculer le centre des marqueurs
    L.Map.include({
        getVisibleMarkers: function() {
            const markers = [];
            this.eachLayer(function(layer) {
                if (layer instanceof L.Marker && this.getBounds().contains(layer.getLatLng())) {
                    markers.push(layer);
                }
            }, this);
            return markers;
        }
    });
}

// Fonction pour aider au debugging
function checkLeafletLoaded() {
    if (typeof L === 'undefined') {
        console.error('Leaflet n\'est pas disponible!');
        return false;
    }
    
    if (!document.getElementById('map')) {
        console.warn('Élément #map non trouvé dans la page');
        return false;
    }
    
    console.log('Leaflet et élément carte sont prêts');
    return true;
}

// Exposer les fonctions utilitaires
window.checkLeafletLoaded = checkLeafletLoaded;
