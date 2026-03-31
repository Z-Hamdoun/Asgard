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

function changeconsole() {
    let choix = document.getElementById("console-select").value;
    const container = document.getElementById("console-container");
    const log = document.getElementById("input-log");
    container.classList.remove('null');  
    log.classList.remove('null');
    if (choix === "terminal") {
        console.log("terminal")
    } else if (choix === "param") {
        container.classList.add('null');
        log.classList.add('null');
        
    }
}

const updateBtnValk = document.getElementById('update-valk');
// Variable globale ou accessible par les deux fonctions
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
    // Si on reçoit un Pong de Valkyrie
    if (data.type === "pong" && data.source === "Valkyrie") {
        
        const rtt = now - data.sent_at; // Temps total aller-retour
        const latency = rtt / 2;        // Un aller simple théorique
        document.getElementById('latency').innerText = latency.toFixed(1);
        
        // Animation du point
        const dot = document.getElementById('status-dot');
        dot.classList.add('online');
        setTimeout(() => dot.classList.remove('online'), 200);
    }
    // Si on reçoit un Pong de Valhalla
    if (data.type === "pong" && data.source === "Valhalla") {
        const rtt = now - data.sent_at; // Temps total aller-retour
        const latency = rtt / 2;        // Un aller simple théorique
        document.getElementById('latency2').innerText = latency.toFixed(1);
        
        // Animation du point
        const dot = document.getElementById('status-dot2');
        dot.classList.add('online');
        setTimeout(() => dot.classList.remove('online'), 200);
    }
    if (data.command === "pull_check" && data.source === "Valkyrie") {
        const dot = document.getElementById('git-dot-valk');
        clearTimeout(valkTimer); 
        dot.classList.remove('noline');
        dot.classList.remove('waitline');
        dot.classList.add('online');
        setTimeout(() => dot.classList.remove('online'), 200);
    }
    if (data.command === "pull_fail" && data.source === "Valkyrie") {
        const dot = document.getElementById('git-dot-valk');
        clearTimeout(valkTimer); 
        dot.classList.remove('noline');
        dot.classList.remove('waitline');
        dot.classList.add('noline');
        setTimeout(() => dot.classList.remove('noline'), 200);
    }
    if (data.command === "pull_check" && data.source === "Valhalla") {
        const dot = document.getElementById('git-dot-valh');
        dot.classList.remove('waitline');
        clearTimeout(valhTimer); 
        dot.classList.remove('noline');
        dot.classList.add('online');
        setTimeout(() => dot.classList.remove('online'), 200);
    }
    if (data.command === "pull_fail" && data.source === "Valhalla") {
        const dot = document.getElementById('git-dot-valh');
        dot.classList.remove('waitline');
        clearTimeout(valhTimer); 
        dot.classList.remove('noline');
        dot.classList.add('noline');
        setTimeout(() => dot.classList.remove('noline'), 200);
    }
};

// CONSOLE

const input = document.getElementById('term-input');
const cursor = document.getElementById('cursor');
const divconsole = document.getElementById('console');

function updateCursor(event) {
    const keyName = event.key;
    if (keyName === "Enter") {
        const nouvelleLigne = document.createElement("div");
        nouvelleLigne.textContent = "helics:~$" + input.value;
        divconsole.appendChild(nouvelleLigne);
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
