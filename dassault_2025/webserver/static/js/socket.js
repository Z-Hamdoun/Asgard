/**
 * Gestion des connexions WebSocket pour les mises à jour en temps réel
 * Ce fichier doit être inclus après les autres dépendances JavaScript (comme leaflet.js)
 */

// Socket.IO client implementation for real-time communication

// Initialize socket connection with better error handling and reconnection
const socket = io({
    reconnection: true,             // Enable reconnection
    reconnectionAttempts: 10,       // Try to reconnect 10 times
    reconnectionDelay: 1000,        // How long to wait before reconnect (1000ms = 1s)
    reconnectionDelayMax: 5000,     // Maximum reconnection delay (5000ms = 5s)
    timeout: 10000,                 // Connection timeout
    autoConnect: true,              // Connect automatically
    transports: ['websocket', 'polling']  // Try WebSocket first, then polling
});
/* HTTPS
"""const socket = io('https://127.0.0.1:5000', {
    upgrade: false,
    reconnection: true,             // Enable reconnection
    reconnectionAttempts: 10,       // Try to reconnect 10 times
    reconnectionDelay: 1000,        // How long to wait before reconnect (1000ms = 1s)
    reconnectionDelayMax: 5000,     // Maximum reconnection delay (5000ms = 5s)
    timeout: 10000,                 // Connection timeout
    autoConnect: true,              // Connect automatically
    transports: ['websocket'],      // Use WebSocket only
    secure: true,                   // Enable secure connection
    rejectUnauthorized: false,      // Don't reject self-signed certificates
    path: '/socket.io/',           // Socket.IO path
    forceNew: true,                // Force a new connection
    rememberUpgrade: false,         // Don't remember transport upgrade
    upgrade: false,                // Disable transport upgrade
    forceBase64: false,            // Don't force base64 encoding
    jsonp: false                   // Disable JSONP
});*/


// Connection status handling
socket.on('connect', function() {
    console.log('Connected to server');
    
    // Request initial positions
    socket.emit('request_positions');
    
    // Add connection status indicator
    if (document.getElementById('connection-status')) {
        document.getElementById('connection-status').textContent = 'Connected';
        document.getElementById('connection-status').className = 'connected';
    }
});

socket.on('disconnect', function() {
    console.log('Disconnected from server');
    
    if (document.getElementById('connection-status')) {
        document.getElementById('connection-status').textContent = 'Disconnected';
        document.getElementById('connection-status').className = 'disconnected';
    }
});

socket.on('connect_error', function(error) {
    console.error('Connection error:', error);
    
    if (document.getElementById('connection-status')) {
        document.getElementById('connection-status').textContent = 'Connection Error';
        document.getElementById('connection-status').className = 'error';
    }
});

// Add reconnection events
socket.on('reconnecting', (attemptNumber) => {
    console.log(`Attempting to reconnect (${attemptNumber})...`);
    if (document.getElementById('connection-status')) {
        document.getElementById('connection-status').textContent = `Reconnecting (${attemptNumber})...`;
        document.getElementById('connection-status').className = 'disconnected';
    }
});

socket.on('reconnect', (attemptNumber) => {
    console.log(`Reconnected after ${attemptNumber} attempts`);
    if (document.getElementById('connection-status')) {
        document.getElementById('connection-status').textContent = 'Connected';
        document.getElementById('connection-status').className = 'connected';
    }
    
    // Re-request positions after reconnection
    socket.emit('request_positions');
});

socket.on('reconnect_error', (error) => {
    console.error('Reconnection error:', error);
    if (document.getElementById('connection-status')) {
        document.getElementById('connection-status').textContent = 'Reconnection failed';
        document.getElementById('connection-status').className = 'error';
    }
});

socket.on('reconnect_failed', () => {
    console.error('Failed to reconnect after all attempts');
    if (document.getElementById('connection-status')) {
        document.getElementById('connection-status').textContent = 'Connection failed';
        document.getElementById('connection-status').className = 'error';
    }
});

// Position updates handling
// TODO: switch to http request
socket.on('/api/position_update', function(positions) {
    try {
        //console.log('Received position update:', positions);
        // Update drone position
        if (positions.drone) {
            updateCoordinateDisplay('drone', positions.drone);
            // Execute updatePosition from script.js if it exists
            
            // If map is initialized and drone marker exists, update its position
            if (typeof updateDronePosition === 'function' && positions.drone.latitude && positions.drone.longitude) {
                updateDronePosition(
                    parseFloat(positions.drone.latitude),
                    parseFloat(positions.drone.longitude),
                    parseFloat(positions.drone.altitude || 0),
                    parseFloat(positions.drone.heading || 0)
                );
            }
        }
        
        // Update plane position
        if (positions.plane) {
            updateCoordinateDisplay('plane', positions.plane);
            
            // If map is initialized and plane marker exists, update its position
            if (typeof updatePlanePosition === 'function' && positions.plane.latitude && positions.plane.longitude) {
                updatePlanePosition(
                    parseFloat(positions.plane.latitude),
                    parseFloat(positions.plane.longitude),
                    parseFloat(positions.plane.altitude || 0),
                    parseFloat(positions.plane.heading || 0)
                );
            }
        }
    } catch (error) {
        console.error('Error handling position update:', error);
    }
});

socket.on('initial_positions', function(positions) {
    console.log('Received initial positions:', positions);
    
    // Process the same way as regular position updates
    socket.emit('position_update', positions);
});

// Update UI elements with new coordinate values
function updateCoordinateDisplay(object, position) {
    try {
        // Update latitude
        const latElement = document.getElementById(`${object}-latitude`);
        if (latElement) {
            latElement.textContent = position.latitude;
            latElement.classList.add('coordinate-update');
            setTimeout(() => latElement.classList.remove('coordinate-update'), 1500);
        }
        
        // Update longitude
        const lngElement = document.getElementById(`${object}-longitude`);
        if (lngElement) {
            lngElement.textContent = position.longitude;
            lngElement.classList.add('coordinate-update');
            setTimeout(() => lngElement.classList.remove('coordinate-update'), 1500);
        }
        
        // Update altitude
        const altElement = document.getElementById(`${object}-altitude`);
        if (altElement) {
            altElement.textContent = position.altitude;
            altElement.classList.add('coordinate-update');
            setTimeout(() => altElement.classList.remove('coordinate-update'), 1500);
        }
        
        // Update heading if available
        const headingElement = document.getElementById(`${object}-heading`);
        if (headingElement && position.heading !== undefined) {
            headingElement.textContent = position.heading;
            headingElement.classList.add('coordinate-update');
            setTimeout(() => headingElement.classList.remove('coordinate-update'), 1500);
        }
        
        // Update speed if available
        const speedElement = document.getElementById(`${object}-speed`);
        if (speedElement && position.speed !== undefined) {
            speedElement.textContent = position.speed;
            speedElement.classList.add('coordinate-update');
            setTimeout(() => speedElement.classList.remove('coordinate-update'), 1500);
        }
    } catch (error) {
        console.error(`Error updating ${object} coordinate display:`, error);
    }
}

// Pause/resume real-time updates
let realTimeEnabled = true;
function toggleRealTime() {
    realTimeEnabled = !realTimeEnabled;
    
    if (realTimeEnabled) {
        // Resume updates
        socket.connect();
        console.log('Real-time updates resumed');
        
        if (document.getElementById('toggle-realtime')) {
            document.getElementById('toggle-realtime').textContent = 'Pauser le temps réel';
        }
    } else {
        // Pause updates
        socket.disconnect();
        console.log('Real-time updates paused');
        
        if (document.getElementById('toggle-realtime')) {
            document.getElementById('toggle-realtime').textContent = 'Reprendre le temps réel';
        }
    }
}

// Expose functions to be used by other scripts
window.socketToggleRealTime = toggleRealTime;