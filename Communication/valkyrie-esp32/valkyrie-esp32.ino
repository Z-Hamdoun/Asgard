#include <ESP32Servo.h>
#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>

// ═══════════════════════════════════════════════════════════════
//  CONFIGURATION MATÉRIELLE (PINS)
// ═══════════════════════════════════════════════════════════════

#define SW0_PIN      25
#define SW1_PIN      26
#define SERVO_PIN    28

HardwareSerial PI_SERIAL(0);

// ═══════════════════════════════════════════════════════════════
//  PARAMÈTRES DE LA PINCE
// ═══════════════════════════════════════════════════════════════

#define SERVO_STOP   1500
#define SERVO_MIN    1000
#define SERVO_MAX    2000
#define DEBOUNCE_MS    25

#define CALIB_TIMEOUT_MS     35000
#define CALIB_OPEN_TIME_MS   30000
#define CATCH_TIMEOUT_MS     20000
#define FAIL_OPEN_TIME_MS    20000
#define CLOSE_EXTRA_TIME_MS   3000

// --- Trapèze de vitesse ---python -m uvicorn Dashboard.app:app --host 0.0.0.0 --port 8000
// La montée évite le pic de courant au démarrage.
// La descente évite le à-coup en fin d'ouverture temporisée.
#define RAMP_UP_MS    1200   // 0 → pleine vitesse
#define RAMP_DOWN_MS  1500   // pleine vitesse → 0 (fin d'ouverture)

// ═══════════════════════════════════════════════════════════════
//  VARIABLES
// ═══════════════════════════════════════════════════════════════

uint8_t broadcastAddress[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

char rx_buffer[250];
int  rx_index = 0;

Servo gripper;

enum class GripState : uint8_t {
    IDLE,
    CALIBRATING,
    STOPPING_TO_OPEN,   // roue libre → rampe descendante avant ouverture (timeout fermeture)
    OPENING,
    CLOSING,
    CLOSING_EXTRA,
    OBJECT_CAUGHT
};

GripState     gripState             = GripState::IDLE;
bool          calibrated            = false;
bool          invertDir             = true;
uint8_t       speedPercent          = 100;
unsigned long actionStartMs         = 0;
unsigned long currentOpenDurationMs = CALIB_OPEN_TIME_MS;
bool          openRampDownStarted   = false;
unsigned long pendingOpenDurationMs = CALIB_OPEN_TIME_MS; // durée d'ouverture après STOPPING_TO_OPEN

// --- Trapèze ---
int           currentPwm  = SERVO_STOP;
int           rampStartPwm = SERVO_STOP;
int           rampEndPwm   = SERVO_STOP;
unsigned long rampStartMs  = 0;
unsigned long rampDurMs    = 0;
bool          ramping      = false;

struct Switch {
    const uint8_t pin;
    bool lastRaw;
    bool stable;
    unsigned long lastChange;
};

Switch sw0 = { SW0_PIN, HIGH, HIGH, 0 };
Switch sw1 = { SW1_PIN, HIGH, HIGH, 0 };

// ═══════════════════════════════════════════════════════════════
//  FONCTIONS TRAPÈZE
// ═══════════════════════════════════════════════════════════════

int pwmForDir(bool closing) {
    int offset = map(speedPercent, 1, 100, 10, 490);
    bool actualClose = closing ^ invertDir;
    return actualClose ? (SERVO_STOP - offset) : (SERVO_STOP + offset);
}

// Démarre une interpolation linéaire de currentPwm vers endPwm en durationMs ms
void startRamp(int endPwm, unsigned long durationMs) {
    rampStartPwm = currentPwm;
    rampEndPwm   = endPwm;
    rampStartMs  = millis();
    rampDurMs    = durationMs;
    ramping      = true;
}

// À appeler à chaque itération de loop() — applique l'interpolation
void applyRamp() {
    if (!ramping) return;
    unsigned long elapsed = millis() - rampStartMs;
    if (elapsed >= rampDurMs) {
        currentPwm = rampEndPwm;
        ramping    = false;
    } else {
        currentPwm = rampStartPwm + (int)((long)(rampEndPwm - rampStartPwm) * elapsed / rampDurMs);
    }
    gripper.writeMicroseconds(currentPwm);
}

// Arrêt immédiat — utilisé sur détection de switch (réactivité max)
void servoStopImmediate() {
    ramping    = false;
    currentPwm = SERVO_STOP;
    gripper.writeMicroseconds(SERVO_STOP);
}

// Rampe montante vers la vitesse de fermeture
void servoStartClose() {
    startRamp(pwmForDir(true), RAMP_UP_MS);
}

// Rampe montante vers la vitesse d'ouverture
void servoStartOpen() {
    startRamp(pwmForDir(false), RAMP_UP_MS);
}

// Rampe descendante vers l'arrêt (fin d'ouverture temporisée)
void servoRampToStop() {
    startRamp(SERVO_STOP, RAMP_DOWN_MS);
}

bool readSwitch(Switch &sw) {
    bool raw = digitalRead(sw.pin);
    if (raw != sw.lastRaw) { sw.lastChange = millis(); sw.lastRaw = raw; }
    if ((millis() - sw.lastChange) >= DEBOUNCE_MS) { sw.stable = sw.lastRaw; }
    return (sw.stable == LOW);
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
    PI_SERIAL.begin(115200);
    delay(500);

    pinMode(SW0_PIN, INPUT_PULLUP);
    pinMode(SW1_PIN, INPUT_PULLUP);
    ESP32PWM::allocateTimer(0);
    gripper.setPeriodHertz(50);
    gripper.attach(SERVO_PIN, SERVO_MIN, SERVO_MAX);
    servoStopImmediate();

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
//  COMMANDES PINCE
// ═══════════════════════════════════════════════════════════════

void handleGripCommand(const String &sub) {
    if (sub == "CALIB") {
        calibrated = false;
        servoStartClose();          // rampe montante → fermeture
        actionStartMs = millis();
        gripState = GripState::CALIBRATING;

    } else if (sub == "OPEN") {
        if (!calibrated) {
            PI_SERIAL.println("GRIP:ERR_NOT_CALIBRATED");
        } else {
            servoStartOpen();       // rampe montante → ouverture
            actionStartMs = millis();
            currentOpenDurationMs = CALIB_OPEN_TIME_MS;
            openRampDownStarted   = false;
            gripState = GripState::OPENING;
        }

    } else if (sub == "CLOSE") {
        if (!calibrated) {
            PI_SERIAL.println("GRIP:ERR_NOT_CALIBRATED");
        } else {
            servoStartClose();      // rampe montante → fermeture
            actionStartMs = millis();
            gripState = GripState::CLOSING;
        }

    } else if (sub == "STOP") {
        servoStopImmediate();
        calibrated = false;
        gripState  = GripState::IDLE;
        PI_SERIAL.println("GRIP:STOPPED");
    }
}

// ═══════════════════════════════════════════════════════════════
//  LOOP
// ═══════════════════════════════════════════════════════════════

void loop() {
    // ----------------------------------------------------------
    //  1. Lecture série Raspberry Pi
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
    //  2. Application de la rampe PWM (trapèze)
    // ----------------------------------------------------------
    applyRamp();

    // ----------------------------------------------------------
    //  3. Machine d'état pince
    // ----------------------------------------------------------
    bool s0 = readSwitch(sw0);
    bool s1 = readSwitch(sw1);
    bool anySwitch = s0 || s1;
    unsigned long now = millis();

    switch (gripState) {

        case GripState::CALIBRATING:
            if (anySwitch) {
                // Moteur stalled contre la butée → arrêt immédiat (pas de rampe)
                servoStopImmediate();
                PI_SERIAL.println("GRIP:CALIB_OK");
                calibrated            = true;
                pendingOpenDurationMs = CALIB_OPEN_TIME_MS;
                gripState = GripState::STOPPING_TO_OPEN; // !ramping déjà vrai → démarre l'ouverture immédiatement
            } else if (now - actionStartMs > CALIB_TIMEOUT_MS) {
                servoStopImmediate();
                gripState = GripState::IDLE;
                PI_SERIAL.println("GRIP:TIMEOUT_CALIB");
            }
            break;

        case GripState::STOPPING_TO_OPEN:
            // Attend la fin de la rampe descendante, puis démarre l'ouverture
            if (!ramping) {
                servoStartOpen();
                actionStartMs         = now;
                currentOpenDurationMs = pendingOpenDurationMs;
                openRampDownStarted   = false;
                gripState = GripState::OPENING;
            }
            break;

        case GripState::OPENING: {
            unsigned long elapsed = now - actionStartMs;
            if (!openRampDownStarted && elapsed >= currentOpenDurationMs - RAMP_DOWN_MS) {
                servoRampToStop();
                openRampDownStarted = true;
            }
            if (elapsed >= currentOpenDurationMs) {
                servoStopImmediate();
                gripState = GripState::IDLE;
                PI_SERIAL.println("GRIP:OPEN_DONE");
            }
            break;
        }

        case GripState::CLOSING:
            if (anySwitch) {
                // Contact → continue à serrer 3s à pleine vitesse
                PI_SERIAL.println("GRIP:CONTACT");
                actionStartMs = now;
                gripState = GripState::CLOSING_EXTRA;
            } else if (now - actionStartMs > CATCH_TIMEOUT_MS) {
                // Timeout → rampe descendante avant réouverture
                PI_SERIAL.println("GRIP:TIMEOUT_CLOSE");
                pendingOpenDurationMs = FAIL_OPEN_TIME_MS;
                servoRampToStop();
                gripState = GripState::STOPPING_TO_OPEN;
            }
            break;

        case GripState::CLOSING_EXTRA:
            // 3s de serrage contre l'objet → arrêt immédiat (moteur stalled, pas de rampe)
            if (now - actionStartMs >= CLOSE_EXTRA_TIME_MS) {
                servoStopImmediate();
                gripState = GripState::OBJECT_CAUGHT;
                PI_SERIAL.println("GRIP:OBJECT_CAUGHT");
            }
            break;

        default:
            break;
    }
}
