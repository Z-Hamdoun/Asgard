#include <SPI.h>
#include <WiFi.h>

// --- CONFIGURATION GÉNÉRALE ---
#define WIFI_SSID       "VideoLink_ESP"
#define WIFI_PASSWORD   "TresSecurePassword"
#define WIFI_PORT       12345

// --- CONFIGURATION SPI (Maître) ---
// Broche Chip Select pour le RPi 2 (Esclave)
#define SPI_CS_RPi2_PIN 5 
#define RPi2_BUFFER_SIZE 4096 

WiFiServer videoServer(WIFI_PORT);
WiFiClient currentClient; 

void setup() {
  Serial.begin(115200);
  Serial.println("\n--- ESP32-B: Maitre SPI / Serveur Wi-Fi ---");

  // 1. Initialisation Wi-Fi en Point d'Accès (AP)
  WiFi.softAP(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("AP cree. IP: ");
  Serial.println(WiFi.softAPIP()); 

  // 2. Demarrage du serveur TCP/IP
  videoServer.begin();
  Serial.print("Serveur TCP demarre sur le port: ");
  Serial.println(WIFI_PORT);

  // 3. Initialisation du mode Maître SPI
  SPI.begin(); // Utilise les broches SPI par defaut
  pinMode(SPI_CS_RPi2_PIN, OUTPUT);
  digitalWrite(SPI_CS_RPi2_PIN, HIGH); // Desactiver le RPi 2 initialement

  Serial.println("SPI configure en mode Maitre.");
}

void loop() {
  // --- PARTIE 1 : Gestion de la Connexion Wi-Fi ---
  if (!currentClient || !currentClient.connected()) {
    currentClient = videoServer.available();
    if (currentClient) {
      Serial.println("Nouvelle connexion client (ESP32-A) etablie.");
    }
    return; // Attendre la connexion
  }
  
  // --- PARTIE 2 : Relais des Donnees (Wi-Fi -> SPI) ---
  if (currentClient.available()) {
    // 1. Lire l'en-tête de taille de la trame (4 bytes)
    byte sizeBuffer[4];
    // Attendre que l'en-tete soit disponible
    if (currentClient.readBytes(sizeBuffer, 4) != 4) {
      // Erreur de lecture de l'en-tete, fermer la connexion
      currentClient.stop();
      return;
    }
    long frameSize = *(long*)sizeBuffer; // Convertir les bytes en long (taille)
    
    // Si la taille est raisonnable et positive
    if (frameSize > 0 && frameSize <= RPi2_BUFFER_SIZE) { 
        
        // Lire le corps de la trame du Wi-Fi
        byte *frameBuffer = (byte*)malloc(frameSize);
        if (!frameBuffer) {
          Serial.println("Erreur: Memoire insuffisante pour la trame.");
          return;
        }
        
        // Lire le corps entier
        size_t bytesRead = currentClient.readBytes(frameBuffer, frameSize);
        
        if (bytesRead == frameSize) {
          // 2. Transfert SPI vers RPi 2 (Esclave)
          
          // Selectionner l'Esclave (RPi 2)
          digitalWrite(SPI_CS_RPi2_PIN, LOW); 
          
          // Envoyer l'en-tete de taille (afin que RPi 2 sache combien lire)
          SPI.transfer(sizeBuffer, 4); 
          
          // Envoyer les donnees de la trame
          // Utiliser un transfert par bloc si l'API le permet, sinon byte par byte
          for (size_t i = 0; i < frameSize; i++) {
            SPI.transfer(frameBuffer[i]);
          }
          
          // Deselectionner l'Esclave
          digitalWrite(SPI_CS_RPi2_PIN, HIGH);
          
          Serial.print("Trame (");
          Serial.print(frameSize);
          Serial.println(" bytes) relayee via SPI.");
        }
        free(frameBuffer);
    }
  }
}