// ==========================================
// VARIABLES GLOBALES ET ELEMENTS DU DOM
// ==========================================
let valkTimer; 
let valhTimer; 

const dassaultLat=47.6013
const dassaultLong=2.0085
const giftLat=48.7097
const gifLong=2.1671
const updateBtnValk = document.getElementById('update-valk');
const updateBtnValh = document.getElementById('update-valh');
const mainBtn = document.getElementById('green-button');
const landBtn = document.getElementById('orange-button');
const stopBtn = document.getElementById('red-button');
const printBtn = document.getElementById("print-log")
const defaultBtn = document.getElementById("defaultBtn")
const requestBtn = document.getElementById("requestBtn")
const sendBtn = document.getElementById("sendBtn")
const sendCoordsBTN = document.getElementById("sendCoordsBtn")
const requestCoordsBTN = document.getElementById("requestCoordsBtn")
const checkValkBtn = document.getElementById("check-valk-btn")
const checkValhBtn = document.getElementById("check-valh-btn")
const checkEvrnBtn = document.getElementById("check-evrn-btn")

const input = document.getElementById('term-input');
const cursor = document.getElementById('cursor');
const divconsole = document.getElementById('console');

// ==========================================
// INITIALISATION
// ==========================================
import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
mermaid.initialize({ startOnLoad: true, theme: 'neutral' });
// Initialisation de la carte (centrée sur le monde)
const map = L.map('map2').setView([ 48.7097, 2.1671], 16);

// Ajout du fond de carte (OpenStreetMap)
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap'
}).addTo(map);

let marker;

// ==========================================
// WEBSOCKET (CONNEXION & PING)
// ==========================================
const ws = new WebSocket("ws://" + window.location.host + "/ws/dashboard");
setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ 
            type: "ping", 
            target: "Valkyrie",
            sent_at: Date.now() 
        }));
        ws.send(JSON.stringify({ 
            type: "ping", 
            target: "Valhalla",
            sent_at: Date.now() 
        }));
    }
}, 1000);

// COMMUNICATION AVEC VALK ET VALH
ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    const now = Date.now();

    // 1. Fonctions utilitaires pour éviter la répétition
    const updateStatusDot = (id, className, duration = 200) => {
        const dot = document.getElementById(id);
        if (!dot) return;
        dot.classList.remove('online', 'noline', 'waitline');
        dot.classList.add(className);
        setTimeout(() => dot.classList.remove(className), duration);
    };

    const addLog = (containerId, text) => {
        const container = document.getElementById(containerId);
        if (!container) return;

        const line = document.createElement("pre"); // Ajoute ces styles pour forcer le retour à la ligne
        line.style.whiteSpace = "pre-wrap";       // Préserve les sauts de ligne ET wrap
        line.style.wordBreak = "break-all";      // Casse les mots trop longs (ex: logs d'erreurs sans espaces)
        line.style.margin = "0";                 // Retire l'espacement par défaut
        line.textContent = text;
        container.appendChild(line);
        container.scrollTop = container.scrollHeight;
    };

    const updateLatency = (id, sentAt) => {
        const element = document.getElementById(id);
        if (element) {
            const latency = (now - sentAt) / 2;
            element.innerText = latency.toFixed(1);
        }
    };

    // 2. Mapping des actions par "command" ou "type"
    // On gère d'abord le cas particulier du PONG
    if (data.type === "pong") {
        const suffix = data.source === "Valkyrie" ? "" : "2";
        updateLatency(`latency${suffix}`, data.sent_at);
        updateStatusDot(`status-dot${suffix}`, 'online');
        return; // On s'arrête ici pour les pongs
    }

    // 3. Gestionnaire de commandes (Dispatcher)
    const sourceSuffix = data.source === "Valkyrie" ? "valk" : "valh";
    const timer = data.source === "Valkyrie" ? valkTimer : valhTimer;

    switch (data.command) {
        case "pull_ack":
            clearTimeout(timer);
            updateStatusDot(`git-dot-${sourceSuffix}`, 'online');
            break;
        
        case "check_ack":
            intern_log(`Toutes les dépendances sont présentes et à jour sur ${data.source}.`)
            break;

        case "check_fail":
            intern_log(`Erreur de dépendance sur ${data.source}`)
            intern_log(data.output)
            break;

        case "pull_fail":
            clearTimeout(timer);
            updateStatusDot(`git-dot-${sourceSuffix}`, 'noline');
            break;

        case "start_main_ack":
            addLog("console", "--- execution de main ---");
            break;

        case "main_log":
            addLog("console", data.output);
            break;
        case "log_ack":
            intern_log(`Log de ${sourceSuffix} reçu`);
            const container = document.getElementById(`${sourceSuffix}-log`);
            container.innerHTML=""
            addLog(`${sourceSuffix}-log`, data.output);
            break;

        case "main_fail":
            addLog("console", `--- Le processus s'est terminé avec l'erreur ${data.output} ---`);
            break;
        case "stop_ack":
            addLog("console", `Processus stoppé proprement.`);
            break;
        case "no_process":
            addLog("console", `Aucun processus en cours.`);
            break;
        case "already_mission":
            addLog("console", `Mission déjà en cours.`);
            break;
        case "param_ack":
            intern_log("Paramètres mis à jour avec succès.");
            break;
        case "coords_ack":
            intern_log("Coordonnées mis à jour avec succès.");
            break;
        case "ask_ack":
            intern_log("Paramètres récupéré avec succès.");
            const data_param = data.data
            document.getElementById("vrai_largage").value = data_param["vrai_largage"];
            document.getElementById("taille_quadrillage").value = data_param["taille_quadrillage"];
            document.getElementById("pas_quadrillage").value = data_param["pas_quadrillage"];
            document.getElementById("radius_acceptance").value = data_param["radius_acceptance"];
            document.getElementById("FOLLOW_MAX_SPEED").value = data_param["FOLLOW_MAX_SPEED"];
            document.getElementById("alt_quadrillage").value = data_param["alt_quadrillage"];
            break
        case "ask_coords_ack":
            const data_coords = data.data

            intern_log("Destination reçu : " + data_coords["lat_mission"] + ", " + data_coords["lng_mission"]);
            setview([ data_coords["lat_mission"], data_coords["lng_mission"]]);

            // Si un marqueur existe déjà, on le déplace, sinon on le crée
            if (marker) {
                marker.setLatLng([ data_coords["lat_mission"], data_coords["lng_mission"]]);
            } else {
                marker = L.marker([ data_coords["lat_mission"], data_coords["lng_mission"]]).addTo(map);
            }

            // Affichage des coordonnées dans l'interface
            document.getElementById('coords').innerText = `Lat: ${data_coords["lat_mission"]}, Lng: ${data_coords["lng_mission"]}`;
    }
};

// ==========================================
// FONCTIONS DE L'INTERFACE UI
// ==========================================


map.on('click', function(e) {
    const lat = e.latlng.lat.toFixed(6);
    const lng = e.latlng.lng.toFixed(6);

    // Si un marqueur existe déjà, on le déplace, sinon on le crée
    if (marker) {
        marker.setLatLng(e.latlng);
    } else {
        marker = L.marker(e.latlng).addTo(map);
    }

    // Affichage des coordonnées dans l'interface
    document.getElementById('coords').innerText = `Lat: ${lat}, Lng: ${lng}`;
});


function setview(coords){
    map.flyTo(coords, 16, {
        animate: true,
        duration: 1.5 // durée du voyage en secondes
    });

}

document.getElementById('gif-view-button').addEventListener('click', function() {
    setview([ giftLat, gifLong]);
});
document.getElementById('dassault-view-button').addEventListener('click', function() {
    // .flyTo() crée une animation fluide de déplacement
    setview([ dassaultLat, dassaultLong]);
});

document.getElementById('gif-marker-button').addEventListener('click', function() {
    // .flyTo() crée une animation fluide de déplacement
    setview([ giftLat, gifLong]);

    // Si un marqueur existe déjà, on le déplace, sinon on le crée
    if (marker) {
        marker.setLatLng([ giftLat, gifLong]);
    } else {
        marker = L.marker([giftLat, gifLong]).addTo(map);
    }

    // Affichage des coordonnées dans l'interface
    document.getElementById('coords').innerText = `Lat: ${giftLat}, Lng: ${gifLong}`;
});

document.getElementById('dassault-marker-button').addEventListener('click', function() {
    // .flyTo() crée une animation fluide de déplacement
    setview([ dassaultLat, dassaultLong]);

    // Si un marqueur existe déjà, on le déplace, sinon on le crée
    if (marker) {
        marker.setLatLng([ dassaultLat, dassaultLong]);
    } else {
        marker = L.marker([ dassaultLat, dassaultLong]).addTo(map);
    }

    // Affichage des coordonnées dans l'interface
    document.getElementById('coords').innerText = `Lat: ${dassaultLat}, Lng: ${dassaultLong}`;
});

function changelog() {
    let choix = document.getElementById("choix").value;
    const valk = document.getElementById("valk-log");
    const valh = document.getElementById("valh-log");
    valk.classList.remove('full', 'null','demi');  
    valh.classList.remove('full', 'null','demi');
    if (choix === "a") {
        valh.classList.add('null');
        valk.classList.add('full');
    } else if (choix === "b") {
        valh.classList.add('full');
        valk.classList.add('null');
    } else if (choix === "c") {
        valh.classList.add('demi');
        valk.classList.add('demi');
    } else {
        valh.classList.add('null');
        valk.classList.add('null');
    }
}

function intern_log(log){
        const line = document.createElement("div");
        line.style.color = "#5cb85c"
        line.textContent = log;
        divconsole.appendChild(line);
        divconsole.scrollTop = divconsole.scrollHeight;
}

// CONSOLE
function updateCursor(event) {
    const keyName = event.key;
    if (keyName === "Enter") {
        const nouvelleLigne = document.createElement("div");
        nouvelleLigne.textContent = "helics:~$" + input.value;
        divconsole.appendChild(nouvelleLigne);
        divconsole.scrollTop = divconsole.scrollHeight;
        const command = {
                command: "terminal_log",
                target: "Valkyrie",
                output:input.value
            };
        ws.send(JSON.stringify(command))
        
        const container = document.getElementById("console-container");
        
        input.value = "";
    }
    const textBeforeCursor = input.value.substring(0, input.selectionStart);

    const tempSpan = document.createElement('span');
    tempSpan.style.font = window.getComputedStyle(input).font;
    tempSpan.style.visibility = 'hidden';
    tempSpan.style.whiteSpace = 'pre';
    tempSpan.innerText = textBeforeCursor;
    document.body.appendChild(tempSpan);
    
    const textWidth = tempSpan.getBoundingClientRect().width;
    cursor.style.transform = `translateX(${textWidth}px)`;
    
    document.body.removeChild(tempSpan);
}

// function setState(ValhState, ValkState) {
//     const diagramValhDefinition = `
//     flowchart TD
//     %% Point de départ
//     Start(( )) --> stabilize_WAIT

//     subgraph STABILIZE
//         subgraph stabilize_grounded [grounded]
//             stabilize_WAIT[WAIT]
//             stabilize_WAIT -- "<span style='color:red; margin: 0 4px;'>mode_change_fail</span>" --> stabilize_WAIT
//         end
//     end

//     subgraph GUIDED
//         subgraph guided_grounded [grounded]
//             stabilize_WAIT -- "<span style='color:#009F00'>mode_change_ok</span>" ---> DISARMED
    
//             DISARMED -- "<span style='color:#009F00'>arm + gps_ok</span>" --> ARMED
//             DISARMED -- "<span style='color:red'>arm + gps_fail</span>" --> DISARMED
//             ARMED -- "<span style='color:red'>takeoff_fail</span>" --> ARMED
//             ARMED -- "<span style='color:red'>disarm</span>" --> DISARMED
//         end

//         subgraph flying
//             STANDBY["STANDBY<br/>fait for ... time units"]
//             ARMED -- "<span style='color:#009F00'>takeoff_ok</span>" --> STANDBY
    
//             STANDBY -- "<span style='color:red'>goto_fail</span>" --> STANDBY
            
//             MOVING["MOVING<br/>- manual takeover if infinite<br/>- tell Valkyrie when closely"]
            
//             %% Police Verte pour Success
//             STANDBY -- "<span style='color:#009F00'>goto_ok</span>" --> MOVING
//             subgraph ON_TARGET
//                 on_target_AIR[FLYING]
//                 MOVING -- "<span style='color:#009F00'>target_reached</span>" --> on_target_AIR

//                 on_target_GROUND[GROUNDED]
//                 on_target_AIR -- standby --> on_target_GROUND
//                 on_target_GROUND -- Valkyrie_finished --> on_target_AIR
//             end
//         end
//     end

//     on_target_AIR -- "<span style='color:#009F00'>mission_finish</span>" --> RTL
//     flying -- "<span style='color:red; margin: 0 4px;'>no_gps</span>" --> LAND
//     RTL --> End(( ))
//     style STABILIZE fill:#f9fff9,stroke:#c0f0c0,stroke-width:4px
//     style stabilize_grounded fill:#f9fff9,stroke:#d0f0d0,stroke-width:2px
//     style GUIDED fill:#f9f9ff,stroke:#c0c0f0,stroke-width:4px
//     style guided_grounded fill:#f9f9ff,stroke:#d0d0f0,stroke-width:2px
//     style flying fill:#f9f9ff,stroke:#d0d0f0,stroke-width:2px
//     linkStyle 1,4,5,6,8,14 stroke:#ff0000,stroke-width:2px
//     linkStyle 2,3,7,9,10,13 stroke:#009f00,stroke-width:2px
    
//         `;
//     const diagramContainerValh = document.getElementById('diagram-container-valh');
//     // Suppression de l'attribut data-processed indispensable pour forcer Mermaid à redessiner
//     diagramContainerValh.removeAttribute('data-processed'); 
//     diagramContainerValh.innerHTML = diagramValhDefinition;
//     mermaid.init(undefined, diagramContainerValh);
//     const diagramValkDefinition = `
// stateDiagram-v2
// classDef highlight fill:#3b82f6,color:white,stroke:#2563eb,stroke-width:2px

// INIT --> LOADING : Démarrer
// LOADING --> SUCCESS : Terminé
// LOADING --> ERROR : Échec
// SUCCESS --> IDLE : Réinitialiser
// ERROR --> IDLE : Réessayer

// class ${ValkState} highlight
//     `;
//     const diagramContainerValk = document.getElementById('diagram-container-valk');
//     diagramContainerValk.removeAttribute('data-processed'); 
//     diagramContainerValk.innerHTML = diagramValkDefinition;
//     mermaid.init(undefined, diagramContainerValk);

// }

// ==========================================
// ECOUTEURS D'ÉVÉNEMENTS (EVENT LISTENERS)
// ==========================================

input.addEventListener('input', updateCursor);
input.addEventListener('keyup', updateCursor);
input.addEventListener('click', updateCursor);

updateBtnValk.onclick = function() {
    if (ws.readyState === WebSocket.OPEN) {
        const command = { command: "git_pull", target: "Valkyrie" };
        ws.send(JSON.stringify(command));
        
        const dot = document.getElementById('git-dot-valk');
        dot.classList.add('waitline');
        
        clearTimeout(valkTimer);
        valkTimer = setTimeout(() => {
            dot.classList.remove('waitline');
            dot.classList.add('noline');
            setTimeout(() => dot.classList.remove('noline'), 200);
        }, 5000);

    } else {
        const dot = document.getElementById('git-dot-valk');
        dot.classList.add('noline');
        setTimeout(() => dot.classList.remove('noline'), 200);
    }
};

updateBtnValh.onclick = function() {
    if (ws.readyState === WebSocket.OPEN) {
        const command = {
            command: "git_pull",
            target: "Valhalla"
        };
        ws.send(JSON.stringify(command));
        const dot = document.getElementById('git-dot-valh');
        dot.classList.add('waitline');
        clearTimeout(valhTimer);
        valhTimer = setTimeout(() => {
            dot.classList.remove('waitline');
            dot.classList.add('noline');
            setTimeout(() => dot.classList.remove('noline'), 200);
        }, 5000);

    } else {
        const dot = document.getElementById('git-dot-valh');
        dot.classList.add('noline');
        setTimeout(() => dot.classList.remove('noline'), 200);
    }
};

mainBtn.onclick = function() {
    if (ws.readyState === WebSocket.OPEN) {
        const command = {
            command: "main_mission",
            target: "Valkyrie"
        };

        intern_log("requête d'execution envoyé");
        ws.send(JSON.stringify(command));
        

    } else {
        intern_log("site offline");
    }
};

landBtn.onclick = function() {
    if (ws.readyState === WebSocket.OPEN) {
        const command = {
            command: "urgency_landing",
            target: "Valkyrie"
        };
        
        intern_log("requête d'atterissage envoyé");
        ws.send(JSON.stringify(command));
        

    } else {
        intern_log("site offline");
    }
};

stopBtn.onclick = function() {
    if (ws.readyState === WebSocket.OPEN) {
        const command = {
            command: "urgency_stop",
            target: "Valkyrie"
        };
        intern_log("requête d'arrêt d'urgence envoyé");
        ws.send(JSON.stringify(command));
        

    } else {
        intern_log("site offline");
    }
};

printBtn.onclick = function() {
    if (ws.readyState === WebSocket.OPEN) {
        const commandvalk = {
            command: "print_log",
            target: "Valkyrie"
        };
        const commandvalh = {
            command: "print_log",
            target: "Valhalla"
        };
        intern_log("requête de log envoyé");
        ws.send(JSON.stringify(commandvalk));
        ws.send(JSON.stringify(commandvalh));
        

    } else {
        intern_log("site offline");
    }
};

defaultBtn.onclick = function() {
    const valeursParDefaut = {
        "vrai_largage": "true", 
        "taille_quadrillage": 10, 
        "pas_quadrillage": 2,
        "radius_acceptance": 1,
        "FOLLOW_MAX_SPEED": 1400,
        "alt_quadrillage": 8
    };
    document.getElementById("vrai_largage").value = valeursParDefaut["vrai_largage"];
    document.getElementById("taille_quadrillage").value = valeursParDefaut["taille_quadrillage"];
    document.getElementById("pas_quadrillage").value = valeursParDefaut["pas_quadrillage"];
    document.getElementById("radius_acceptance").value = valeursParDefaut["radius_acceptance"];
    document.getElementById("FOLLOW_MAX_SPEED").value = valeursParDefaut["FOLLOW_MAX_SPEED"];
    document.getElementById("alt_quadrillage").value = valeursParDefaut["alt_quadrillage"];
}

requestBtn.onclick = function() {
    const valeursWait = {
        "vrai_largage": "...", 
        "taille_quadrillage": "...", 
        "pas_quadrillage": "...",
        "radius_acceptance": "...",
        "FOLLOW_MAX_SPEED": "...",
        "alt_quadrillage": "..."
    };
    document.getElementById("vrai_largage").value = valeursWait["vrai_largage"];
    document.getElementById("taille_quadrillage").value = valeursWait["taille_quadrillage"];
    document.getElementById("pas_quadrillage").value = valeursWait["pas_quadrillage"];
    document.getElementById("radius_acceptance").value = valeursWait["radius_acceptance"];
    document.getElementById("FOLLOW_MAX_SPEED").value = valeursWait["FOLLOW_MAX_SPEED"];
    document.getElementById("alt_quadrillage").value = valeursWait["alt_quadrillage"];
    const message = {
        "command": "ask_config",
        "target": "Valkyrie",
    };

    if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(message));
        intern_log("Envoi de la requette de configuration");
    } else {
        intern_log("site offline");
    }
}

sendBtn.onclick = function() {
    const inputLargage = document.getElementById("vrai_largage").value;
    const isLargageVrai = (inputLargage.toLowerCase() === "true"); // Convertit en Booléen

    const configData = {
        "vrai_largage": isLargageVrai,
        "taille_quadrillage": parseInt(document.getElementById("taille_quadrillage").value, 10),
        "pas_quadrillage": parseInt(document.getElementById("pas_quadrillage").value, 10),
        "radius_acceptance": parseInt(document.getElementById("radius_acceptance").value, 10),
        "FOLLOW_MAX_SPEED": parseInt(document.getElementById("FOLLOW_MAX_SPEED").value, 10),
        "alt_quadrillage": parseInt(document.getElementById("alt_quadrillage").value, 10)
    };

    // 2. On prépare le message global pour le WebSocket
    const messagevalh = {
        "command": "update_config",
        "target": "Valhalla",
        "data": configData // On intègre nos paramètres ici
    };
    const messagevalk = {
        "command": "update_config",
        "target": "Valkyrie",
        "data": configData // On intègre nos paramètres ici
    };


    if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(messagevalh));
        ws.send(JSON.stringify(messagevalk));
        intern_log("Envoi de la nouvelle configuration");
    } else {
        intern_log("site offline");
    }
}



sendCoordsBTN.onclick = function() {
    if (marker) {
        const position = marker.getLatLng();
        const configData = {
            "lat":position.lat,
            "lng":position.lng
        };
        
        const messagevalh = {
            "command": "update_coords",
            "target": "Valhalla",
            "data": configData // On intègre nos paramètres ici
        };

        if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(messagevalh));
            intern_log("Destination envoyée : " + position.lat + ", " + position.lng);
    
        } else {
            intern_log("site offline");
        }
    } else {
        intern_log("Aucun point sélectionné. Cliquez sur la carte d'abord.");
    }
}

requestCoordsBtn.onclick = function() {
    const message = {
        "command": "ask_coords",
        "target": "Valkyrie"
    };

    if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(message));
        intern_log("Envoi de la requette de configuration");
    } else {
        intern_log("site offline");
    }
}

checkValkBtn.onclick = function(){
    const message = {
        "command": "check_V",
        "target": "Valkyrie"
    };

    if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(message));
        intern_log("Check Valkyrie");
    } else {
        intern_log("site offline");
    }   
}

checkValhBtn.onclick = function(){
    const message = {
        "command": "check_V",
        "target": "Valhalla"
    };

    if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(message));
        intern_log("Check Valhalla");
    } else {
        intern_log("site offline");
    }   
}

checkEvrnBtn.onclick = function(){
    const message = {
        "command": "check_E",
        "target": "Valkyrie"
    };
    if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(message));
        intern_log("Check tout le monde");
    } else {
        intern_log("site offline");
    }   
}