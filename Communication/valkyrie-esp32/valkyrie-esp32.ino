#include <ESP32Servo.h>
#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>

// ═══════════════════════════════════════════════════════════════
//  CONFIGURATION MATÉRIELLE (PINS)
// ═══════════════════════════════════════════════════════════════

#define SW0_PIN      25 // Switch 0
#define SW1_PIN      26 // Switch 1
#define SERVO_PIN    28 // Fil Signal de la Pince

// Configuration UART matériel
// On utilise l'UART0 par défaut de l'ESP32 (broches TX et RX imprimées sur la carte)
HardwareSerial PI_SERIAL(0); 

// ═══════════════════════════════════════════════════════════════
//  PARAMÈTRES ET TEMPORISATIONS DE LA PINCE
// ═══════════════════════════════════════════════════════════════

#define SERVO_STOP   1500
#define SERVO_MIN    1000
#define SERVO_MAX    2000
#define DEBOUNCE_MS    25

// --- Logique Temporelle ---
#define CALIB_TIMEOUT_MS     35000 // 35s max pour trouver les switchs à l'allumage
#define CALIB_OPEN_TIME_MS   30000 // 30s d'ouverture normale (post-calib ou manuelle)
#define CATCH_TIMEOUT_MS     20000 // 20s max de fermeture pour essayer d'attraper l'objet
#define FAIL_OPEN_TIME_MS    20000 // 20s d'ouverture si rien n'a été attrapé
#define CLOSE_EXTRA_TIME_MS   3000 // 3s de serrage supplémentaire une fois le switch touché

// ═══════════════════════════════════════════════════════════════
//  VARIABLES ESP-NOW ET PINCE
// ═══════════════════════════════════════════════════════════════

uint8_t broadcastAddress[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

char rx_buffer[250];
int  rx_index = 0;

Servo gripper;

enum class GripState : uint8_t {
    IDLE,
    CALIBRATING,
    OPENING,
    CLOSING,
    CLOSING_EXTRA,
    OBJECT_CAUGHT
};

GripState     gripState      = GripState::IDLE;
bool          calibrated     = false;
bool          invertDir      = true; // Mettre à 'false' si la pince tourne à l'envers
uint8_t       speedPercent   = 100;
unsigned long actionStartMs  = 0;
unsigned long currentOpenDurationMs = CALIB_OPEN_TIME_MS; 

struct Switch {
    const uint8_t pin;
    bool lastRaw;
    bool stable;
    unsigned long lastChange;
};

Switch sw0 = { SW0_PIN, HIGH, HIGH, 0 };
Switch sw1 = { SW1_PIN, HIGH, HIGH, 0 };

// ═══════════════════════════════════════════════════════════════
//  FONCTIONS UTILITAIRES — PINCE
// ═══════════════════════════════════════════════════════════════

int pwmForDir(bool closing) {
    int offset = map(speedPercent, 1, 100, 10, 490);
    bool actualClose = closing ^ invertDir;
    return actualClose ? (SERVO_STOP - offset) : (SERVO_STOP + offset);
}

void servoStop()  { gripper.writeMicroseconds(SERVO_STOP); }
void servoClose() { gripper.writeMicroseconds(pwmForDir(true)); }
void servoOpen()  { gripper.writeMicroseconds(pwmForDir(false)); }

bool readSwitch(Switch &sw) {
    bool raw = digitalRead(sw.pin);
    if (raw != sw.lastRaw) { sw.lastChange = millis(); sw.lastRaw = raw; }
    if ((millis() - sw.lastChange) >= DEBOUNCE_MS) { sw.stable = sw.lastRaw; }
    return (sw.stable == LOW); // LOW car on utilise INPUT_PULLUP
}

// ═══════════════════════════════════════════════════════════════
//  CALLBACKS ESP-NOW
// ═══════════════════════════════════════════════════════════════

void OnDataRecv(const esp_now_recv_info *info, const uint8_t *data, int len) {
    for (int i = 0; i < len; i++) PI_SERIAL.write(data[i]);
    PI_SERIAL.write('\n');
}

void OnDataSent(const uint8_t *mac, esp_now_send_status_t status) {}

// ═══════════════════════════════════════════════════════════════
//  SETUP
// ═══════════════════════════════════════════════════════════════

void setup() {
    PI_SERIAL.setRxBufferSize(1024);
    PI_SERIAL.setTxBufferSize(1024);
    
    // Initialisation native sur les broches TX0/RX0 par défaut de la carte ESP32
    PI_SERIAL.begin(115200);
    
    delay(500);

    // --- Pince ---
    pinMode(SW0_PIN, INPUT_PULLUP);
    pinMode(SW1_PIN, INPUT_PULLUP);
    ESP32PWM::allocateTimer(0);
    gripper.setPeriodHertz(50);
    gripper.attach(SERVO_PIN, SERVO_MIN, SERVO_MAX);
    servoStop();

    // --- WiFi + ESP-NOW ---
    WiFi.mode(WIFI_STA);
    esp_wifi_set_channel(1, WIFI_SECOND_CHAN_NONE);

    if (esp_now_init() == ESP_OK) {
        esp_now_register_recv_cb(OnDataRecv);
        esp_now_register_send_cb((esp_now_send_cb_t)OnDataSent);

        esp_now_peer_info_t peer = {};
        memcpy(peer.peer_addr, broadcastAddress, 6);
        peer.channel = 1;
        peer.encrypt = false;
        esp_now_add_peer(&peer);
    }

    PI_SERIAL.println("GRIP:READY");
}

// ═══════════════════════════════════════════════════════════════
//  TRAITEMENT D'UNE COMMANDE PINCE (préfixe "GRIP:")
// ═══════════════════════════════════════════════════════════════

void handleGripCommand(const String &sub) {
    if (sub == "CALIB") {
        calibrated = false;
        servoClose();
        actionStartMs = millis();
        gripState = GripState::CALIBRATING;

    } else if (sub == "OPEN") {
        if (!calibrated) {
            PI_SERIAL.println("GRIP:ERR_NOT_CALIBRATED");
        } else {
            servoOpen();
            actionStartMs = millis();
            currentOpenDurationMs = CALIB_OPEN_TIME_MS; // 30s pour ouverture manuelle
            gripState = GripState::OPENING;
        }

    } else if (sub == "CLOSE") {
        if (!calibrated) {
            PI_SERIAL.println("GRIP:ERR_NOT_CALIBRATED");
        } else {
            servoClose();
            actionStartMs = millis();
            gripState = GripState::CLOSING;
        }

    } else if (sub == "STOP") {
        servoStop();
        calibrated = false;
        gripState = GripState::IDLE;
        PI_SERIAL.println("GRIP:STOPPED");
    }
}

// ═══════════════════════════════════════════════════════════════
//  LOOP
// ═══════════════════════════════════════════════════════════════

void loop() {
    // ----------------------------------------------------------
    //  1. Lecture série depuis la Raspberry Pi
    // ----------------------------------------------------------
    while (PI_SERIAL.available() > 0) {
        char c = PI_SERIAL.read();

        if (c == '\n') {
            rx_buffer[rx_index] = '\0';
            String msg = String(rx_buffer);
            msg.trim();
            rx_index = 0;

            if (msg.length() == 0) continue;

            if (msg.startsWith("GRIP:")) {
                handleGripCommand(msg.substring(5));
            } else {
                esp_now_send(broadcastAddress, (uint8_t *)msg.c_str(), msg.length());
            }

        } else if (c != '\r') {
            if (rx_index < 248) rx_buffer[rx_index++] = c;
            else rx_index = 0;
        }
    }

    // ----------------------------------------------------------
    //  2. Machine d'état pince
    // ----------------------------------------------------------
    bool s0 = readSwitch(sw0);
    bool s1 = readSwitch(sw1);
    bool anySwitch = s0 || s1;

    switch (gripState) {
        case GripState::CALIBRATING:
            if (anySwitch) {
                // Switch touché -> On lance l'ouverture de 30s
                PI_SERIAL.println("GRIP:CALIB_OK");
                servoOpen();
                actionStartMs = millis();
                currentOpenDurationMs = CALIB_OPEN_TIME_MS; // 30s
                gripState = GripState::OPENING;
                calibrated = true;
            } else if (millis() - actionStartMs > CALIB_TIMEOUT_MS) {
                servoStop();
                gripState = GripState::IDLE;
                PI_SERIAL.println("GRIP:TIMEOUT_CALIB");
            }
            break;

        case GripState::OPENING:
            // Utilisé pour la fin de calibration, l'ouverture manuelle ET l'ouverture de sécurité
            if (millis() - actionStartMs >= currentOpenDurationMs) {
                servoStop();
                gripState = GripState::IDLE;
                PI_SERIAL.println("GRIP:OPEN_DONE");
            }
            break;

        case GripState::CLOSING:
            if (anySwitch) {
                // Contact détecté ! On serre encore 3s pour sécuriser
                PI_SERIAL.println("GRIP:CONTACT");
                actionStartMs = millis();
                gripState = GripState::CLOSING_EXTRA;
            } else if (millis() - actionStartMs > CATCH_TIMEOUT_MS) {
                // Rien attrapé après 20s -> On prévient la Pi et on rouvre pour 20s
                PI_SERIAL.println("GRIP:TIMEOUT_CLOSE");
                servoOpen();
                actionStartMs = millis();
                currentOpenDurationMs = FAIL_OPEN_TIME_MS; // 20s de réouverture
                gripState = GripState::OPENING;
            }
            break;

        case GripState::CLOSING_EXTRA:
            if (millis() - actionStartMs >= CLOSE_EXTRA_TIME_MS) {
                // Serrage de 3s terminé
                servoStop();
                gripState = GripState::OBJECT_CAUGHT;
                PI_SERIAL.println("GRIP:OBJECT_CAUGHT");
            }
            break;

        default:
            break;
    }
}