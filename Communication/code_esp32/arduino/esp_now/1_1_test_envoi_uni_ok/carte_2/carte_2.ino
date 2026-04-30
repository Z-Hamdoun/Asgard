#include <esp_now.h>
#include <WiFi.h>

// Définition de la structure (identique à l'émetteur)
typedef struct Message {
  int Compteur; // La valeur du potentiomètre
  char* Hello; // La valeur du bouton poussoir
};

Message Mon_message; //crée une variable de type Message

// Fonction de réception des données
void OnDataRecv(const uint8_t * mac_addr, const uint8_t *incomingData, int len) {
  char macStr[18];
   
  // Copier les données reçues dans Message
  memcpy(&Mon_message, incomingData, sizeof(Mon_message));
  Serial.print(Mon_message.Hello);
  Serial.println(Mon_message.Compteur);
}

void setup() {
  Serial.begin(115200);
  WiFi.mode(WIFI_STA); // Mode station pour l'ESP32

  // Initialisation de ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Erreur d'initialisation d'ESP-NOW");
    return;
  }

  // Enregistrer la fonction de réception
esp_now_register_recv_cb(esp_now_recv_cb_t(OnDataRecv));
  Serial.print(Mon_message.Hello);
  Serial.println(Mon_message.Compteur);
}

void loop() {
  // On affiche les données reçues toutes les 500 ms
  delay(1000); // Attente de 500 ms
}