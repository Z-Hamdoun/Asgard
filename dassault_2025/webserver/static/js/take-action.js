// fonction pour prendre une action
export function take_action(onject) {
    let object_id = onject.getAttribute("data-object");
    let action_id = onject.getAttribute("data-action");

    if (!object_id || !action_id) {
        console.error("Données manquantes !");
        return;
    }

    // Changer la couleur du bouton pour indiquer que l'action est en cours
    onject.style.filter = "grayscale(100%)"; // Jaune (en attente)

    // Envoi de la requête à Flask
    fetch("/api/take_action", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ object_id: object_id, action_id: action_id })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            onject.style.filter = "grayscale(0%)"; // Vert (succès)
        } else {
            onject.style.filter = "hue-rotate(260deg)"; // Rouge (échec)
            setTimeout(() => {
                onject.style.filter = "grayscale(0%)";
            }, 2000);
        }
    })
    .catch(error => {
        console.error("Erreur lors de la requête:", error);
        onject.style.filter = "hue-rotate(260deg)"; // Rouge (échec)
    });
}