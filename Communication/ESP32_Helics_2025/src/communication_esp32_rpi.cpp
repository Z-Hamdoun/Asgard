#include <Arduino.h>
// --- Configuration des paramètres ---
// Vitesse de communication (doit correspondre au BAUD_RATE du RPi)
#define BAUD_RATE 115200 

// Définit le port série que nous allons utiliser sur l'ESP32.
// Serial est le port USB/Debug (souvent utilisé).
// Serial1 (ou Serial2) est typiquement utilisé pour la communication avec un autre appareil (comme un RPi).
// ATTENTION : Les broches par défaut pour Serial1 sont GPIO9 (RX) et GPIO10 (TX)
// Vérifiez la documentation de votre carte ESP32.
HardwareSerial& RpiSerial = Serial1; 

// Variables pour stocker les coordonnées reçues
float g_targetLatitude = 0.0;
float g_targetLongitude = 0.0;

// Variables pour la lecture des données série
const int MAX_LINE_LENGTH = 128; // Taille maximale du buffer de réception
char inputBuffer[MAX_LINE_LENGTH]; 
int bufferIndex = 0;

// ------------------------------------------------------------------------------------------------

void setup() {
  // 1. Initialisation du port de débogage (USB)
  // Utile pour afficher les messages de statut et de débogage sur le moniteur série de l'IDE.
  Serial.begin(115200);
  Serial.println("\n--- ESP32 pret pour la communication UART ---");

  // 2. Initialisation du port UART dédié à la communication avec le RPi
  // On utilise RpiSerial (Serial1) avec le BAUD_RATE défini.
  // Les broches sont souvent remappables, mais on utilise les valeurs par defaut ou celles definies.
  RpiSerial.begin(BAUD_RATE);
  // Optionnel : remapper les broches si besoin (ex: RpiSerial.begin(BAUD_RATE, SERIAL_8N1, 16, 17); )
  Serial.print("Port UART RPi (Serial1) initialise a ");
  Serial.print(BAUD_RATE);
  Serial.println(" bauds.");
}

// ------------------------------------------------------------------------------------------------

/**
 * @brief Analyse la ligne de donnees 'Clé:Valeur' envoyee par le RPi.
 * La fonction utilise strtok pour diviser la chaine par le separateur.
 * @param line La chaine de caracteres complete (ex: "LAT:48.8584,LON:2.2945\\n")
 */
void parse_data(char* line) {
  // On travaille sur une copie de la ligne car strtok modifie la chaine originale
  char tempLine[MAX_LINE_LENGTH];
  strncpy(tempLine, line, MAX_LINE_LENGTH);
  
  // 1. Decoupage par la virgule (',')
  char* token = strtok(tempLine, ","); 
  
  while (token != NULL) {
    // 2. Trouver le separateur deux-points (':')
    char* colon_pos = strchr(token, ':'); 
    
    if (colon_pos != NULL) {
      // 3. Extraire la Cle et la Valeur
      *colon_pos = '\0'; // Remplace le ':' par un terminateur de chaine pour isoler la Cle
      char* key = token;
      char* value_str = colon_pos + 1; // La valeur commence juste apres l'ancien ':'
      
      // Conversion de la valeur en nombre
      float value_float = atof(value_str); // atof convertit la chaine en float
      
      // 4. Traitement des donnees (Cle:Valeur)
      if (strcmp(key, "LAT") == 0) {
        g_targetLatitude = value_float;
        Serial.print("Nouv. LAT cible: ");
        Serial.println(g_targetLatitude, 6); // Affichage avec 6 decimales
      } else if (strcmp(key, "LON") == 0) {
        g_targetLongitude = value_float;
        Serial.print("Nouv. LON cible: ");
        Serial.println(g_targetLongitude, 6);
      }
      // Ajouter d'autres cles ('SPD', 'CMD', etc.) ici si necessaire

    }
    // Passer au jeton suivant
    token = strtok(NULL, ",");
  }
}

/**
 * @brief Envoie un message de statut au RPi (l'ESP32 agit en emetteur).
 * @param key La cle du message (ex: "STATUT")
 * @param value La valeur du message (ex: "OK")
 */
void send_status_message(const char* key, const char* value) {
  // Formate la chaine (ex: "STATUT:OK\\n")
  char outputBuffer[64]; 
  snprintf(outputBuffer, sizeof(outputBuffer), "%s:%s\n", key, value);
  
  // Ecrit le message sur le port serie dedie au RPi
  RpiSerial.print(outputBuffer);
  
  // Affichage de debogage (sur le port USB)
  Serial.print("-> Envoye au RPi: ");
  Serial.print(outputBuffer); // print ajoute deja le \n
}


// ------------------------------------------------------------------------------------------------

void loop() {
  // --- PARTIE 1 : RECEPTION ET DECODAGE DES DONNEES DU RPI ---
  
  // Verifie si des donnees sont disponibles sur le port serie RPi
  while (RpiSerial.available()) {
    char incomingChar = RpiSerial.read();
    
    // 1. Verification du marqueur de fin de ligne ('\n')
    if (incomingChar == '\n' || incomingChar == '\r') { 
      // Si la fin du message est detectee, on termine la chaine
      inputBuffer[bufferIndex] = '\0'; 
      
      // Verifie que le buffer n'est pas vide avant l'analyse
      if (bufferIndex > 0) {
        Serial.print("<- Recu du RPi: ");
        Serial.println(inputBuffer);
        
        // Appel de la fonction d'analyse
        parse_data(inputBuffer); 
      }
      
      // Reinitialisation pour le prochain message
      bufferIndex = 0;
      
    } else if (bufferIndex < MAX_LINE_LENGTH - 1) {
      // 2. Stockage des caracteres si ce n'est pas la fin de ligne
      inputBuffer[bufferIndex] = incomingChar;
      bufferIndex++;
    } 
    // Si bufferIndex atteint MAX_LINE_LENGTH - 1, le caractere est ignore (overflow protection)
  }
  
  // --- PARTIE 2 : LOGIQUE APPLICATIVE ET ENVOI DE REPONSES ---

  // Exemple de logique : apres avoir recu de nouvelles coordonnees, 
  // l'ESP32 envoie un message de confirmation au RPi
  static bool first_run = true;
  if (g_targetLatitude != 0.0 && first_run) {
    send_status_message("STATUT", "COORD_RECUES");
    first_run = false;
  }
  
  // Exemple d'envoi de telemetrie de l'ESP32 au RPi
  // send_status_message("TEMP", "25.5"); // Envoi d'une temperature fictive
  
  delay(10); // Petit delai pour laisser l'ESP32 faire d'autres taches
}