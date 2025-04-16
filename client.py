import socket
import random
import time
from threading import Thread, Lock
from collections import deque

CLIENT_ID = "Specter"
PACKET_LIMIT = 10_000_000
INIT_SEQ = 70000
PKT_LEN = 4
FLOW_SIZE = 1
SEQ_WRAP = 65536

_sent = 0
_attempts = 0
_cur_seq = INIT_SEQ
_wsize = FLOW_SIZE
_sched = []
_misses = deque()
_resend_log = [[], [], [], []]
_seen = set()
_cycle = 0
_created = 0
_is_linked = False

_sock = None

log_drop = open(f"drops_{int(time.time())}.csv", "w")
log_drop.write("sid,tstamp\n")
drp_lock = Lock()

log_win = open(f"winlog_{int(time.time())}.csv", "w")
log_win.write("wsize,tstamp\n")
win_lock = Lock()

def init_socket():
    global _sock, _sent, _attempts, _cur_seq, _wsize, _sched, _misses, _resend_log, _cycle, _created, _is_linked

    host = socket.gethostname()
    port = 4001

    if _is_linked:
        return 1

    try:
        _sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _sock.connect((host, port))
    except Exception as e:
        print("NetFail:", str(e))
        return -1

    _is_linked = True
    flag = "SYN" if _sent < 10 or _sent > (PACKET_LIMIT * 0.99) else "RCN"
    _sock.send(f"{flag} {CLIENT_ID[:10]}".encode())

    msg = _sock.recv(2048).decode()
    if msg == "NEW":
        print("Linked Fresh")
    elif msg.startswith("OLD"):
        print("Resyncing...")
        _sock.send("SND".encode())
        state = eval(_sock.recv(4096).decode())
        _sent = state['pkt_rec_cnt']
        _attempts = state['pkt_rec_cnt']
        _cur_seq = state['seq_num']
    elif msg.startswith("SND"):
        sync_info = f'{{"pkt_success_sent": int({_sent}), "seq_num": int({_cur_seq})}}'
        _sock.sendall(sync_info.encode())
    else:
        print("Server unreachable!")
        exit()

    try:
        emit_stream()
    except Exception as e:
        print(e)
        summarize()
        reconnect()

def reconnect():
    global _is_linked
    _is_linked = False
    try:
        while not _is_linked:
            init_socket()
            time.sleep(1)
    except:
        summarize()
        reconnect()

def should_drop():
    return random.random() < 0.01

def record_miss(seq, t, loop):
    pid = f"{seq}_{loop}"
    _seen.add((seq, t))
    if pid in _resend_log[0]:
        if pid in _resend_log[1]:
            if pid in _resend_log[2]:
                _resend_log[3].append(pid)
            else:
                _resend_log[2].append(pid)
        else:
            _resend_log[1].append(pid)
    else:
        _resend_log[0].append(pid)

    with drp_lock:
        log_drop.write(f"{seq},{t}\n")

def note_window(ws, t):
    with win_lock:
        log_win.write(f"{ws},{t}\n")

def emit_stream():
    global _sock, _sent, _attempts, _cur_seq, _wsize, _sched, _misses, _seen, _resend_log, _cycle, _created

    if _cur_seq < SEQ_WRAP:
        print(f"Resuming @ seq: {_cur_seq}, Already sent {_sent}")

    while _sent < PACKET_LIMIT:
        _sched = []
        wait_ack = 0
        flagged = False

        for _ in range(_wsize):
            if _created < PACKET_LIMIT:
                if _cur_seq % 1000 == 1 and len(_misses):
                    while len(_sched) <= _wsize and _misses:
                        _sched.append(_misses.popleft())
                    break

                if _cur_seq + PKT_LEN > SEQ_WRAP:
                    _cur_seq = 1
                    _cycle += 1
                else:
                    _cur_seq += PKT_LEN

                _created += 1
                _sched.append(_cur_seq)
            else:
                while len(_sched) <= _wsize and _misses:
                    _sched.append(_misses.popleft())
                break

        for item in _sched:
            _attempts += 1
            if should_drop():
                _misses.append(item)
                flagged = True
                Thread(target=record_miss, args=(item, time.time(), _cycle)).start()
                if _wsize > 1:
                    _wsize = max(1, _wsize // 2)
                    Thread(target=note_window, args=(_wsize, time.time())).start()
            else:
                wait_ack += 1
                _sock.sendall((str(item) + " ").encode())
                _sent += 1

        _sock.settimeout(0.5)
        try:
            feed = _sock.recv(8192).decode()
            confirmations = list(map(int, feed.split()))
        except:
            wait_ack = 0
            return reconnect()

        for ack in confirmations:
            if ack and _wsize < 2048:
                _wsize += 1
            wait_ack -= 1

        Thread(target=note_window, args=(_wsize, time.time())).start()
        _sock.settimeout(None)

        if _attempts % 10 == 0:
            print(f"Dispatched {_attempts} packets...")

    summarize()
    shutdown()

def summarize():
    print(f"Client: {socket.gethostbyname(socket.gethostname())}")
    print(f"Sent: {_attempts}")
    print("Retries - 1x:{0} 2x:{1} 3x:{2} 4x:{3}".format(*map(len, _resend_log)))

def shutdown():
    time.sleep(1)
    log_drop.close()
    log_win.close()
    _sock.close()

def reset_state():
    global _sent, _attempts, _cur_seq, _wsize, _sched, _misses, _seen, _resend_log, _cycle, _created
    _sent = 0
    _attempts = 0
    _cur_seq = INIT_SEQ
    _wsize = FLOW_SIZE
    _sched = []
    _misses = deque()
    _seen = set()
    _resend_log = [[], [], [], []]
    _cycle = 0
    _created = 0

# if __name__ == '__main__':
#     t0 = time.time()
#     reconnect()
#     t1 = time.time()
#     print("Elapsed:", t1 - t0)

if __name__ == '__main__':
    t0 = time.time()
    try:
        reconnect()
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user. Shutting down...")
    finally:
        summarize()
        shutdown()
        t1 = time.time()
        print("Elapsed:", t1 - t0)
