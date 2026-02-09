#include <iostream>
#include <fcntl.h>
#include <termios.h>
#include <unistd.h>
#include <cstring>
#include <chrono>
#include <cstdint>
#include "../../../../../mavlink/ardupilotmega/mavlink.h"

#define BUFFER_SIZE 1400 // max of 250 bytes

// Cette version ne parse pas les messages, il sépare uniquement de manière temporelle

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

static auto program_start = std::chrono::steady_clock::now();
uint32_t micros() {
    auto now = std::chrono::steady_clock::now();
    return static_cast<uint32_t>(std::chrono::duration_cast<std::chrono::microseconds>(now - program_start).count());
}

int main() {
    const char* in_port = "/tmp/ttyV1";
    const char* out_port = "/tmp/ttyV2";
    int baudrate = B57600;
    const uint32_t timeout_micros = (int)(1.0 / 57600 * 1E6) * 20;


    int fd_in = open_serial(in_port, baudrate);
    int fd_out = open_serial(out_port, baudrate);

    if (fd_in < 0 || fd_out < 0) {
        std::cerr << "Failed to open serial ports.\n";
        return 1;
    }

    std::cout << "Listening on " << in_port << " and forwarding to " << out_port << std::endl;

    mavlink_message_t msg;
    mavlink_message_t msg2;
    mavlink_status_t status;
    mavlink_status_t status2;
    uint8_t buf[1024];
    uint8_t buf2[1024];

    uint8_t buf_send[BUFFER_SIZE];
    uint16_t buf_size = 0;
    uint32_t send_timeout = 0;



    while (true) {
        int n = read(fd_in, buf, sizeof(buf));
        if (n > 0) {
            write(fd_out, buf, n);
        } 
        int nn = read(fd_out, buf2, sizeof(buf2));
        if (nn > 0) {
            write(fd_in, buf2, nn);
        }

    }

    close(fd_in);
    close(fd_out);
    return 0;
}
