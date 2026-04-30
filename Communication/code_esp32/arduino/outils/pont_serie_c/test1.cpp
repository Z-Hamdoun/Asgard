#include <iostream>
#include <fcntl.h>
#include <termios.h>
#include <unistd.h>
#include <cstring>
#include <chrono>
#include <cstdint>
#include "../../../../../mavlink/ardupilotmega/mavlink.h"


float LAT_ORIGINE = -31.9508512;
float LON_ORIGINE = 115.863278;
float ALT_ORIGINE = 10;

// Il faut demander attitude de manière régulière, python : 
/*self.master.mav.command_long_send(
            target_system, # target_system
            0, # target_component
            mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, # command
            1, # confirmation
            msg_id, # param1 (Message ID)
            int(10**6/rate), # param2 (Interval)
            0,0,0,0,0 # param3-7 (unused)
        )*/

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
    const char* uwb_port = "/tmp/ttyV5";
    int baudrate = B57600;
    const uint32_t timeout_micros = (int)(1.0 / 57600 * 1E6) * 20;


    int fd_in = open_serial(in_port, baudrate);
    int fd_out = open_serial(out_port, baudrate);
    int fd_uwb = open_serial(uwb_port, baudrate);

    if (fd_in < 0 || fd_out < 0 || fd_uwb < 0) {
        std::cerr << "Failed to open serial ports.\n";
        return 1;
    }

    std::cout << "Listening on " << in_port << " and forwarding to " << out_port << std::endl;
    std::cout << "Listening on " << uwb_port << " for UWB positions" << std::endl;

    mavlink_message_t msg;
    mavlink_message_t msg2;
    mavlink_message_t msg3;
    mavlink_status_t status;
    mavlink_status_t status2;
    mavlink_status_t status3;
    uint8_t buf[1024];
    uint8_t buf2[1024];
    uint8_t buf3[1024];

    float roll = 0.0f, pitch = 0.0f, yaw = 0.0f;
    float vpe_x = 0.0f, vpe_y = 0.0f, vpe_z = 0.0f;

    while (true) {
        int n = read(fd_in, buf, sizeof(buf));
        if (n > 0) {
            for (int i = 0; i < n; ++i) {
                uint8_t msg_received = mavlink_parse_char(MAVLINK_COMM_0, buf[i], &msg, &status);
                if (msg_received && !(msg.sysid == 255 && msg.compid == 230)) {
                    // Successfully parsed a full MAVLink message
                    uint8_t tx_buf[MAVLINK_MAX_PACKET_LEN];
                    uint16_t len = mavlink_msg_to_send_buffer(tx_buf, &msg);
                    write(fd_out, tx_buf, len);
                    if ((msg.sysid >= 11 && msg.sysid <= 25) && msg.msgid == 30) {
                        // store roll, pitch, yaw values
                        mavlink_attitude_t attitude;
                        mavlink_msg_attitude_decode(&msg, &attitude);
                        roll = attitude.roll;
                        pitch = attitude.pitch;
                        yaw = attitude.yaw;
                        std::cout << "roll: " << yaw << std::endl;
                    }
                    std::cout << "aOK" << unsigned(msg_received) << " seq: " << unsigned(msg.seq) << std::endl;
                }
                else if (msg_received != 0) {
                    std::cout << "a" << unsigned(msg_received) << std::endl;
                }
            }
        } 
        int nn = read(fd_out, buf2, sizeof(buf2));
        if (nn > 0) {
            for (int i = 0; i < nn; ++i) {
                uint8_t msg_received2 = mavlink_parse_char(MAVLINK_COMM_1, buf2[i], &msg2, &status2);
                if (msg_received2) {
                    // Successfully parsed a full MAVLink message
                    uint8_t tx_buf[MAVLINK_MAX_PACKET_LEN];
                    uint16_t len = mavlink_msg_to_send_buffer(tx_buf, &msg2);
                    write(fd_in, tx_buf, len);
                    std::cout << "bOK" << unsigned(msg_received2) << " seq: " << unsigned(msg2.seq) << std::endl;
                }
                else if (msg_received2 != 0) {
                    std::cout << "b" << unsigned(msg_received2) << std::endl;
                }
            }
        }

        int nnn = read(fd_uwb, buf3, sizeof(buf3));
        if (nnn > 0) {
            for (int i = 0; i < nnn; ++i) {
                uint8_t msg_received3 = mavlink_parse_char(MAVLINK_COMM_1, buf3[i], &msg3, &status3);
                if (msg_received3) {
                    // Successfully parsed a full MAVLink message
                    //uint8_t tx_buf[MAVLINK_MAX_PACKET_LEN];
                    //uint16_t len = mavlink_msg_to_send_buffer(tx_buf, &msg2);
                    //write(fd_in, tx_buf, len);
                    if (msg3.msgid == 102){
                        // Store the position values from the VISION_POSITION_ESTIMATE msg
                        mavlink_vision_position_estimate_t vpe;
                        mavlink_msg_vision_position_estimate_decode(&msg3, &vpe);
                        vpe_x = vpe.x;
                        vpe_y = vpe.y;
                        vpe_z = vpe.z;
                        std::cout << "VISION_POSITION_ESTIMATE -> x: " << vpe_x
                                  << " y: " << vpe_y << " z: " << vpe_z << std::endl;
                        //std::cout << "cOK" << unsigned(msg_received3) << "                        msgid: " << msg3.msgid << std::endl;
                    }
                }
                else if (msg_received3 != 0) {
                    std::cout << "c" << unsigned(msg_received3) << std::endl;
                }
            }
        }

        int fd_out_pos = fd_in;
        // Send VISION_POSITION_ESTIMATE at 10 Hz
        static uint32_t last_send_time = 0;
        uint32_t current_time = micros();
        if (current_time - last_send_time >= 100000) { // 100ms = 10 Hz
            last_send_time = current_time;
            
            mavlink_message_t vpe_msg;
            mavlink_vision_position_estimate_t vpe_data = {};
            vpe_data.x = vpe_x;
            vpe_data.y = vpe_y;
            vpe_data.z = vpe_z;
            /*vpe_data.roll = roll;
            vpe_data.pitch = pitch;
            vpe_data.yaw = yaw;*/
            vpe_data.roll = 0;
            vpe_data.pitch = 0;
            vpe_data.yaw = 0;
            vpe_data.usec = current_time;


            // Il faut s'assurer que le GPS denied marche bien avec ces valeurs de compid
            mavlink_msg_vision_position_estimate_encode(255, 191, &vpe_msg, &vpe_data);
            uint8_t tx_buf[MAVLINK_MAX_PACKET_LEN];
            uint16_t len = mavlink_msg_to_send_buffer(tx_buf, &vpe_msg);
            write(fd_out_pos, tx_buf, len);
            std::cout << "vpe_data.x: " << vpe_data.x
                      << " y: " << vpe_data.y
                      << " z: " << vpe_data.z
                      << " roll: " << vpe_data.roll
                      << " pitch: " << vpe_data.pitch
                      << " yaw: " << vpe_data.yaw
                      << std::endl;
        }

        
        static uint32_t last_send_time_origin = 0;
        if (current_time - last_send_time_origin >= 1000000) { // 10000ms = 0.1 Hz
            last_send_time_origin = current_time;
            // Send GPS_GLOBAL_ORIGIN (lat/lon in 1e7 deg, alt in mm)
            int32_t lat_orig = static_cast<int32_t>(-31.9508512 * 1e7);
            int32_t lon_orig = static_cast<int32_t>(115.864278 * 1e7);
            int32_t alt_orig = static_cast<int32_t>(10.0 * 1000.0); // meters -> mm

            mavlink_message_t ggo_msg;
            mavlink_set_gps_global_origin_t ggo_data = {};
            ggo_data.altitude = alt_orig;
            ggo_data.latitude = lat_orig;
            ggo_data.longitude = lon_orig;
            ggo_data.target_system = 11;
            ggo_data.time_usec = current_time;

            //mavlink_message_t origin_msg;
            // pack: (sysid, compid, msg, target_system, latitude, longitude, altitude)
            //mavlink_msg_gps_global_origin_pack(255, 191, &origin_msg, 11, lat_orig, lon_orig, alt_orig);
            mavlink_msg_set_gps_global_origin_encode(255, 191, &ggo_msg, &ggo_data);
            
            uint8_t tx_buf[MAVLINK_MAX_PACKET_LEN];
            uint16_t len = mavlink_msg_to_send_buffer(tx_buf, &ggo_msg);
            write(fd_out_pos, tx_buf, len);


            // ==== COMMAND_INT ====
            mavlink_message_t shp_msg;
            mavlink_set_home_position_t shp_data = {};
            shp_data.altitude = ALT_ORIGINE;
            shp_data.latitude = (int32_t)(LAT_ORIGINE * 1e7);
            shp_data.longitude = (int32_t)(LON_ORIGINE * 1e7);
            shp_data.target_system = 11;

            mavlink_msg_set_home_position_encode(255, 191, &shp_msg, &shp_data);
            uint8_t tx_buf2[MAVLINK_MAX_PACKET_LEN];
            uint16_t len2 = mavlink_msg_to_send_buffer(tx_buf2, &shp_msg);
            write(fd_out_pos, tx_buf2, len2);

            /*mavlink_msg_command_int_pack(
            255, 191, &cmd_msg,
            11, 1,
            0,
            179,
            0, 0,
            0, 0, 0, 0,
            (int32_t)(LAT_ORIGINE * 1e7),
            (int32_t)(LON_ORIGINE * 1e7),
            ALT_ORIGINE
            );
            uint8_t buf5[MAVLINK_MAX_PACKET_LEN];
            uint16_t len5 = mavlink_msg_to_send_buffer(buf5, &cmd_msg);
            write(fd_out_pos, buf5, len5);*/
            
        }
    }

    close(fd_in);
    close(fd_out);
    return 0;
}
