#include <esp_now.h>
#include <WiFi.h>

// L'adresse Mac du récepteur
#include "../../card_info.h" // Adjust the path as needed
#define ESPNOW_WIFI_CHANNEL GLOBAL_WIFI_CHANNEL
#define MacAdress MAC_CARTE_2 // counterpart MAC address

// Définition de la structure (identique au récepteur)
typedef struct Message {
  int Compteur; // La valeur du potentiomètre
  char* Hello; // La valeur du bouton poussoir
};

Message Mon_message; //crée une variable de type Message

esp_now_peer_info_t peerInfo; // Crée une variable pour stocker les informations du partage

void OnDataSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
  Serial.print("\r\nLast Packet Send Status:\t");
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "Delivery Success" : "Delivery Fail");
} // Cette fonction permet d'afficher si le message a été correctement livré

// Fonction de réception des données
void OnDataRecv(const uint8_t * mac_addr, const uint8_t *incomingData, int len) {
  char macStr[18];
   
  // Copier les données reçues dans Message
  memcpy(&Mon_message, incomingData, sizeof(Mon_message));
  Serial.print(Mon_message.Hello);
  Serial.println(Mon_message.Compteur);
}

void sendData(Message m){
  esp_err_t result = esp_now_send(MacAdress, (uint8_t *) &m, sizeof(m)); // Envoie les données de Mon_message
  if (result == ESP_OK) {
    Serial.println("Sent with success");
  }
  else {
    Serial.println("Error sending the data");
  } // Vérifie si l'envoi a fonctionné
}

void setup(){
  Serial.begin(115200);
  WiFi.mode(WIFI_STA); // Mode station pour l'ESP32

  if (esp_now_init() != ESP_OK) {
    Serial.println("Erreur d'initialisation d'ESP-NOW");
    return;}
}

void loop(){}