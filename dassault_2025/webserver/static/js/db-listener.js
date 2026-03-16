export { add_db_listener, init_db_listener };

const dbListeners = {};

/**
 * Enregistre une fonction de rappel pour un modèle et une opération spécifiques.
 * @param {string} model - Le nom du modèle (par exemple, 'Log').
 * @param {string} operation - Le type d'opération ('insert', 'update', 'delete').
 * @param {function} callback - La fonction à appeler pour chaque élément de données.
 */
function add_db_listener(model, operation, callback) {
    const key = `${model}:${operation}`;
    if (!dbListeners[key]) {
        dbListeners[key] = [];
    }
    dbListeners[key].push(callback);
}

function init_db_listener(socket) {
    // Écoute des événements 'db_change' émis par le serveur
    socket.on('db_change', function(data) {
        const key = `${data.model}:${data.operation}`;
        const listeners = dbListeners[key];
        if (listeners) {
            data.data.forEach(item => {
                    listeners.forEach(callback => callback(item));
                });
            }
        }
    );
}
