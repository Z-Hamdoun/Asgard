// Librairies pour ESP Now et le wifi
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

char* Hell = "Hello world ";
int Compteu = 0;

Message Mon_message; //crée une variable de type Message

esp_now_peer_info_t peerInfo; // Crée une variable pour stocker les informations du partage

void OnDataSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
  Serial.print("\r\nLast Packet Send Status:\t");
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "Delivery Success" : "Delivery Fail");
} // Cette fonction permet d'afficher si le message a été correctement livré

void setup() {
  Serial.begin(115200); // Initialise le moniteur serial
  WiFi.mode(WIFI_STA); // Active le wifi 
if (esp_now_init() != ESP_OK) {
  Serial.println("Error initializing ESP-NOW");
  return; // affiche les éventuels problèmes d'initialisation d'ESP now
}

esp_now_register_send_cb(OnDataSent); // permet d'envoyer l'accusé de réception

memcpy(peerInfo.peer_addr, MacAdress, 6);
peerInfo.channel = ESPNOW_WIFI_CHANNEL;
peerInfo.encrypt = false; // Ajoute un pair

if (esp_now_add_peer(&peerInfo) != ESP_OK){
  Serial.println("Failed to add peer");
  return;
} // Affiche s'il y a eu un problème lors de l'ajout du pair

}

void loop() {
  
  Compteu++;
  Mon_message.Hello = Hell;
  Mon_message.Compteur = Compteu;
esp_err_t result = esp_now_send(MacAdress, (uint8_t *) &Mon_message, sizeof(Mon_message)); // Envoie les données de Mon_message

if (result == ESP_OK) {
  Serial.println("Sent with success");
}
else {
  Serial.println("Error sending the data");
} // Vérifie si l'envoi a fonctionné

Serial.print(Mon_message.Hello);
Serial.println(Mon_message.Compteur);

delay(1000);

}