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

const updateBtnValk = document.getElementById('update-valk');
// Variable globale ou accessible par les deux fonctions

const missionBtn =document.getAnimations

let valkTimer; 
let valhTimer; 

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
const updateBtnValh = document.getElementById('update-valh');
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



const ws = new WebSocket("ws://" + window.location.host + "/ws");
setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ 
            type: "ping", 
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

        const line = document.createElement("div");
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

        case "pull_fail":
            clearTimeout(timer);
            updateStatusDot(`git-dot-${sourceSuffix}`, 'noline');
            break;

        case "start_main_ack":
            addLog("valk-log", "--- execution de main ---");
            break;

        case "main_log":
            addLog("valk-log", data.output);
            break;

        case "main_fail":
            addLog("valk-log", `--- Le processus s'est terminé avec l'erreur ${data.output} ---`);
            break;
        case "stop_ack":
            addLog("valk-log", `Processus stoppé proprement.`);
            break;
        case "no_process":
            addLog("valk-log", `Aucun processus en cours.`);
            break;
        case "already_mission":
            addLog("valk-log", `Mission déjà en cours.`);
            break;
    }
};

// CONSOLE

function changeconsole() {
    let choix = document.getElementById("console-select").value;
    const container = document.getElementById("console-container");
    const log = document.getElementById("input-log");
    const param = document.getElementById("param-container")
    const mission = document.getElementById("mission-container")
    param.classList.remove('null');
    container.classList.remove('null');  
    mission.classList.remove('null')
    log.classList.remove('null');
    if (choix === "terminal") {
        param.classList.add("null")
        mission.classList.add("null")

    } else if (choix === "param") {

        container.classList.add('null');
        log.classList.add('null');
        
    }
}

const input = document.getElementById('term-input');
const cursor = document.getElementById('cursor');
const divconsole = document.getElementById('console');

function updateCursor(event) {
    const keyName = event.key;
    if (keyName === "Enter") {
    const nouvelleLigne = document.createElement("div");
    nouvelleLigne.textContent = "helics:~$" + input.value;
    divconsole.appendChild(nouvelleLigne);
    divconsole.scrollTop = container.scrollHeight;
    const command = {
            type:"log",
            command: "terminal_log",
            target: "Valkyrie",
            output: input.value

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
input.addEventListener('input', updateCursor);
input.addEventListener('keyup', updateCursor);
input.addEventListener('click', updateCursor);


const mainBtn = document.getElementById('green-button');
mainBtn.onclick = function() {
    if (ws.readyState === WebSocket.OPEN) {
        const command = {
            command: "main_mission",
            target: "Valkyrie"
        };

        const container = document.getElementById("valk-log");
        const line = document.createElement("div");
        line.textContent = "requête d'execution envoyé";
        container.appendChild(line);
        container.scrollTop = container.scrollHeight;
        ws.send(JSON.stringify(command));
        

    } else {
        console.log("echec")
    }
};

const landBtn = document.getElementById('orange-button');
landBtn.onclick = function() {
    if (ws.readyState === WebSocket.OPEN) {
        const command = {
            command: "urgency_landing",
            target: "Valkyrie"
        };
        const container = document.getElementById("valk-log");
        const line = document.createElement("div");
        line.textContent = "requête d'atterissage envoyé";
        container.appendChild(line);
        container.scrollTop = container.scrollHeight;
        ws.send(JSON.stringify(command));
        

    } else {
        console.log("echec")
    }
};

const stopBtn = document.getElementById('red-button');
stopBtn.onclick = function() {
    if (ws.readyState === WebSocket.OPEN) {
        const command = {
            command: "urgency_stop",
            target: "Valkyrie"
        };
        const container = document.getElementById("valk-log");
        const line = document.createElement("div");
        line.textContent = "requête d'arrêt d'urgence envoyé";
        container.appendChild(line);
        container.scrollTop = container.scrollHeight;
        ws.send(JSON.stringify(command));
        

    } else {
        console.log("echec")
    }
};
