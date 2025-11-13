#include <SPI.h>
#include <WiFi.h>

// --- CONFIGURATION GÉNÉRALE ---
#define WIFI_SSID       "VideoLink_ESP" // Doit correspondre à l'AP de l'ESP32-B
#define WIFI_PASSWORD   "TresSecurePassword"
#define ESP32B_IP       IPAddress(192, 168, 4, 1) // IP par défaut de l'AP
#define WIFI_PORT       12345
#define SPI_BUFFER_SIZE 4096 // Taille max du buffer SPI pour une trame (4KB)

// --- CONFIGURATION SPI (Esclave) ---
// Broches ESP32 (Vérifiez votre carte si vous utilisez SPI2)
#define SPI_MISO_PIN    19 // Master In Slave Out (Pour l'envoi de l'ESP32 vers RPi, non utilisé ici)
#define SPI_MOSI_PIN    23 // Master Out Slave In (Pour la réception du RPi)
#define SPI_SCK_PIN     18 // Serial Clock
#define SPI_SS_PIN      5  // Slave Select (Chip Select)

// Objets pour la communication
WiFiClient wifiClient;
byte spiRxBuffer[SPI_BUFFER_SIZE];
volatile bool packetReady = false;
volatile size_t bytesReceived = 0;

// Déclaration de la fonction de gestion SPI (ISR)
void IRAM_ATTR spi_slave_interrupt_handler();

// ----------------------------------------------------------------------

void setup() {
  Serial.begin(115200);
  Serial.println("\n--- ESP32-A: Esclave SPI / Client Wi-Fi ---");

  // 1. Initialisation Wi-Fi en Station (Client)
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnecté au point d'acces de l'ESP32-B.");

  // 2. Initialisation du mode Esclave SPI
  // La broche SS (CS) est definie dans spi_slave_initialize
  // Les broches sont configurées dans le mode Esclave
  // Note: Nous utilisons l'API ESP-IDF pour une gestion SPI Esclave plus robuste
  // (Nécessite des définitions d'API non standard ici, donc on simule avec SPI.beginSlave)

  // Configuration de base :
  pinMode(SPI_SS_PIN, INPUT_PULLUP);
  // (Dans un code réel, on utiliserait l'API SPISlave de l'ESP32)
  
  // Cette ligne est conceptuelle et doit être remplacée par l'API SPISlave pour être fonctionnelle:
  // SPI.beginSlave(SPI_SCK_PIN, SPI_MISO_PIN, SPI_MOSI_PIN, SPI_SS_PIN); 

  Serial.println("Mode Esclave SPI pret.");
}

void loop() {
  // --- PARTIE 1 : Maintenir la Connexion Wi-Fi ---
  if (!wifiClient.connected()) {
    Serial.print("Tentative de connexion au serveur TCP...");
    if (wifiClient.connect(ESP32B_IP, WIFI_PORT)) {
      Serial.println("OK.");
    } else {
      Serial.println("Échec de la connexion.");
      delay(2000);
      return;
    }
  }

  // --- PARTIE 2 : Lecture SPI et Relais Wi-Fi ---
  // RPi 1 (Maitre) demarre la transaction en baissant SS
  
  // Cette section est une SIMULATION du processus de réception SPI:
  
  // Si le RPi 1 a envoyé une trame (simuler la detection d'une trame SPI complete)
  if (/* Ici, le code réel détecterait une trame SPI complète */ false) { 
    // Example: bytesReceived = 1000;
    
    // Lire la trame complète du buffer SPI (gestion des en-têtes de taille, etc.)
    // ...

    if (wifiClient.connected() && bytesReceived > 0) {
      // Envoi de l'en-tête de taille (4 bytes)
      wifiClient.write((byte*)&bytesReceived, 4);
      
      // Envoi de la trame binaire elle-même
      size_t written = wifiClient.write(spiRxBuffer, bytesReceived); 
      
      // Nettoyage du buffer
      bytesReceived = 0;
      
      Serial.print("Trame de ");
      Serial.print(written);
      Serial.println(" bytes envoyee via Wi-Fi.");
    }
  }

  // Ici, la boucle principale devrait continuellement vider le buffer SPI de l'Esclave 
  // pour éviter l'encombrement.
  
  // Le code réel d'un SPI Esclave robuste se fait principalement par des interruptions.
}