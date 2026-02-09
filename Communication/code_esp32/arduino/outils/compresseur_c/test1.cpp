#include <iostream>
#include <fcntl.h>
#include <termios.h>
#include <unistd.h>
#include <cstring>
#include <chrono>
#include <cstdint>
#include <algorithm>
#include "../../../../../mavlink/ardupilotmega/mavlink.h"

int open_serial(const char* portname, int baudrate) {
    int fd = open(portname, O_RDWR | O_NOCTTY | O_NDELAY);
    if (fd == -1) {
        perror("open_serial");
        return -1;
    }

    struct termios options;
    tcgetattr(fd, &options);
    cfsetispeed(&options, baudrate);
    cfsetospeed(&options, baudrate);
    options.c_cflag |= (CLOCAL | CREAD);
    options.c_cflag &= ~CSIZE;
    options.c_cflag |= CS8;
    options.c_cflag &= ~PARENB;
    options.c_cflag &= ~CSTOPB;
    options.c_cflag &= ~CRTSCTS;
    options.c_lflag = 0;
    options.c_oflag = 0;
    options.c_iflag = 0;
    tcflush(fd, TCIFLUSH);
    tcsetattr(fd, TCSANOW, &options);

    return fd;
}


// taille max du buffer : 1470 bytes
const uint16_t MAX_ESP_BUFFER_SIZE = 1470;

// nombre maximum de paquets dans le buffer
const uint8_t MAX_PACKETS_IN_BUFFER = 1;

// timeout d'envoi de messages
uint16_t TIMEOUT_BUFFER_SEND = 100;

// liste des messages qu'il faut envoyer directement
const uint8_t ID_DIRECT_SEND_LEN = 1;
uint32_t packets_id_direct_send[ID_DIRECT_SEND_LEN] = {0};

// liste des messages qu'on peut stocker en plusieurs exemplaires
const uint8_t ID_STORE_LEN = 1;
uint32_t packets_id_store[ID_STORE_LEN] = {110};

// définition du buffer global
uint8_t global_tx_buf[MAX_ESP_BUFFER_SIZE];
uint16_t global_tx_buf_len = 0;
uint32_t first_packet_millis = 0;
uint32_t packets_id_in_buffer[MAX_PACKETS_IN_BUFFER]; // liste des types de paquets stoqués dans le buffer
uint8_t number_of_packets_in_buffer = 0;

// helper: milliseconds since program start
static auto program_start = std::chrono::steady_clock::now();
uint32_t millis() {
    auto now = std::chrono::steady_clock::now();
    return static_cast<uint32_t>(std::chrono::duration_cast<std::chrono::milliseconds>(now - program_start).count());
}

// helper: check if value is in array (length passed)
bool is_in_array(const uint32_t *arr, size_t arr_len, uint32_t value) {
    for (size_t i = 0; i < arr_len; ++i) {
        if (arr[i] == value) return true;
    }
    return false;
}

// add a message buffer (tx_buf of length msg_len) into the global buffer
void add_msg_to_buf(int port, const uint8_t *tx_buf, uint16_t msg_len, uint32_t msgid) {
    // if first packet, set timestamp
    if (global_tx_buf_len == 0) {
        first_packet_millis = millis();
    }

    // checks if buffer won't go over its limits or timeout
    if (global_tx_buf_len + msg_len > MAX_ESP_BUFFER_SIZE || (number_of_packets_in_buffer + 1) >= MAX_PACKETS_IN_BUFFER || millis() > first_packet_millis + TIMEOUT_BUFFER_SEND) {
        if (global_tx_buf_len > 0) {
            write(port, global_tx_buf, global_tx_buf_len);
            std::cout << "sending buffer cause over limit, buf_pkts : " << static_cast<int>(number_of_packets_in_buffer) << " len_buf : " << static_cast<int>(global_tx_buf_len + msg_len) << std::endl;
        }
        

        // reset buffer
        global_tx_buf_len = 0;
        first_packet_millis = millis();
        // clean packets_id_in_buffer
        for (uint8_t i = 0; i < MAX_PACKETS_IN_BUFFER; ++i) packets_id_in_buffer[i] = 0;
        number_of_packets_in_buffer = 0;
    }

    // ensure we don't overflow (msg_len should already be checked)
    if (msg_len > 0 && (global_tx_buf_len + msg_len) <= MAX_ESP_BUFFER_SIZE) {
        // copy bytes into global buffer1;
        memcpy(global_tx_buf + global_tx_buf_len, tx_buf, msg_len);

        // add msgid to packets_id_in_buffer if not already present
        if (!is_in_array(packets_id_in_buffer, number_of_packets_in_buffer, msgid)) {
            if (number_of_packets_in_buffer < MAX_PACKETS_IN_BUFFER) {
                packets_id_in_buffer[number_of_packets_in_buffer++] = msgid;
            }
        }

        global_tx_buf_len += msg_len;
    }
}


// new_message: decide whether to buffer or flush immediately
int new_message(int port, const mavlink_message_t &msg, const uint8_t *tx_buf, uint16_t msg_len){
    // add message to local/global buffer
    add_msg_to_buf(port, tx_buf, msg_len, msg.msgid);

    // decide if we need to send now:
    // - if msgid is in direct send list
    // - OR if msgid is NOT allowed to be stored (not in packets_id_store) AND it is already present in buffer (we want only one copy)
    bool direct = is_in_array(packets_id_direct_send, ID_DIRECT_SEND_LEN, msg.msgid);
    bool can_store = is_in_array(packets_id_store, ID_STORE_LEN, msg.msgid);
    bool already_in_buffer = is_in_array(packets_id_in_buffer, number_of_packets_in_buffer, msg.msgid);

    if (direct) {// || (!can_store && already_in_buffer)) {
        if (global_tx_buf_len > 0) {
            write(port, global_tx_buf, global_tx_buf_len);
            std::cout << "sending buffer cause direct " << static_cast<int>(number_of_packets_in_buffer) << std::endl;
            // reset buffer after send
            global_tx_buf_len = 0;
            first_packet_millis = millis();
            for (uint8_t i = 0; i < MAX_PACKETS_IN_BUFFER; ++i) packets_id_in_buffer[i] = 0;
            number_of_packets_in_buffer = 0;
        }
    }

    return 0;
}


int main() {
    const char* in_port = "/tmp/ttyV1";
    const char* out_port = "/tmp/ttyV2";
    int baudrate = B115200;

    int fd_in = open_serial(in_port, baudrate);
    int fd_out = open_serial(out_port, baudrate);

    if (fd_in < 0 || fd_out < 0) {
        std::cerr << "Failed to open serial ports.\n";
        return 1;
    }

    std::cout << "Forwarding messages between " << in_port << " and " << out_port << std::endl;

    mavlink_message_t msg1;
    mavlink_status_t status1;
    uint8_t buf1[1024];

    mavlink_message_t msg2;
    mavlink_status_t status2;
    uint8_t buf2[1024];

    while (true) {
        int n = read(fd_in, buf1, sizeof(buf1));
        if (n > 0) {
            for (int i = 0; i < n; ++i) {
                if (mavlink_parse_char(MAVLINK_COMM_0, buf1[i], &msg1, &status1)) {
                    // Successfully parsed a full MAVLink message
                    uint8_t tx_buf[MAVLINK_MAX_PACKET_LEN];
                    uint16_t len = mavlink_msg_to_send_buffer(tx_buf, &msg1);
//                    new_message(fd_out, msg, tx_buf, len);
                    write(fd_out, tx_buf, len);
                }
            }
        }
        int n2 = read(fd_out, buf2, sizeof(buf2));
        if (n2 > 0) {
            for (int i = 0; i < n2; ++i) {
                int parsing_status = mavlink_parse_char(MAVLINK_COMM_0, buf2[i], &msg2, &status2);
                if (parsing_status == 1) {
                    // Successfully parsed a full MAVLink message
                    uint8_t tx_buf[MAVLINK_MAX_PACKET_LEN];
                    uint16_t len = mavlink_msg_to_send_buffer(tx_buf, &msg2);
                    write(fd_in, tx_buf, len);
                }
                else {//} if (parsing_status == 2){
                    std::cout << "error parsing message : " << parsing_status << " number of parse error : " << static_cast<int>(status2.parse_error) << " seq " << static_cast<int>(status2.current_rx_seq) << std::endl;
                }
            }
        } else {
            usleep(1000); // avoid busy loop
        }
        /*if (millis() > first_packet_millis + TIMEOUT_BUFFER_SEND) {
            if (global_tx_buf_len > 0) {
                write(fd_out, global_tx_buf, global_tx_buf_len);
                std::cout << "sending buffer cause timeout " << static_cast<int>(number_of_packets_in_buffer) << std::endl;
            }
            global_tx_buf_len = 0;
            first_packet_millis = millis();
            // clean packets_id_in_buffer
            for (uint8_t i = 0; i < MAX_PACKETS_IN_BUFFER; ++i) packets_id_in_buffer[i] = 0;
            number_of_packets_in_buffer = 0;
        }*/
    }

    close(fd_in);
    close(fd_out);
    return 0;
}
