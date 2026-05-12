from pymavlink import mavutil
import time

PORT_LEADER = "127.0.0.1:14550" 
PORT_FOLLOWER = "127.0.0.1:14560" 

def main():

    try:
        leader = mavutil.mavlink_connection(f'udp:{PORT_LEADER}')
        follower = mavutil.mavlink_connection(f'udp:{PORT_FOLLOWER}')
    except Exception as e:
        return

    leader.wait_heartbeat()
    
    follower.wait_heartbeat()

    msg_count = 0
    last_print = time.time()

    while True:
        msg = leader.recv_match(blocking=False)
        
        if msg:
            if msg.get_type() == 'GLOBAL_POSITION_INT':
                
                msg_bytes = msg.get_msgbuf()
                
                follower.write(msg_bytes)
                
                msg_count += 1
                
                if time.time() - last_print > 2:
                    print(f"[PONT] {msg_count} positions relayées (Source ID préservé).")
                    last_print = time.time()
                    msg_count = 0

        time.sleep(0.0001) 

if __name__ == "__main__":
    main()