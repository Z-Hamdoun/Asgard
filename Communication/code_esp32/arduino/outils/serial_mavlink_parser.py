from pymavlink import mavutil
import sys
import argparse
import time


def show(port = "/dev/pts/26", baudrate=115200):


    master = mavutil.mavlink_connection(
        port, baud=baudrate
    )
    old_t = time.time()
    n=0
    while True:
        m = master.recv_match(blocking=True)
        print(m._header.seq, m.get_srcSystem(), m.get_srcComponent(), m.get_type())
        if old_t + 1 < time.time():
            print("#"*100, master.packet_loss())
            old_t = time.time()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-p", "--port",
        type=str,
        required=True,
        help="Adresse de l'appareil série"
    )

    parser.add_argument(
        "-b", "--baudrate",
        type=int,
        required=False,
        help="Baudrate",
        default=115200
    )

    args = parser.parse_args(sys.argv[1:])
    print(args)

    show(args.port, args.baudrate)

