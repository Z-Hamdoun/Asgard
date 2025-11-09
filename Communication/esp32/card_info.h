#pragma once

// MAC addresses for all cards
// Pour les trouver, il faut flasher un des codes et noter l'adresse mac affichée ici
static uint8_t MAC_CARTE_1[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
static uint8_t MAC_CARTE_2[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};


static uint8_t MAC_BROADCAST[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
const uint8_t GLOBAL_WIFI_CHANNEL = 6;
// Add more as needed

// WIFI_PHY_RATE_LORA_500K 	-> 42
// WIFI_PHY_RATE_2M_L		-> 1
// WIFI_PHY_RATE_9M 		-> 15
