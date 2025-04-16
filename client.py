import socket
import random
import time
from threading import Thread, Lock, Event
from collections import deque

CLIENT_ID = "Specter"
PACKET_LIMIT = 10_000_000
INIT_SEQ = 0
PKT_LEN = 4
FLOW_SIZE = 1
SEQ_WRAP = 65536

_exit_flag = Event()
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

drp_lock = Lock()
win_lock = Lock()

log_drop = open(f"drops_{int(time.time())}.csv", "w")
log_drop.write("sid,tstamp\n")
log_win = open(f"winlog_{int(time.time())}.csv", "w")
log_win.write("wsize,tstamp\n")

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

def shutdown():
    try:
        if _sock:
            _sock.shutdown(socket.SHUT_RDWR)
            _sock.close()
    except:
        pass
    log_drop.close()
    log_win.close()

def summarize():
    print(f"Client: {socket.gethostbyname(socket.gethostname())}")
    print(f"Sent: {_attempts}")
    print("Retries - 1x:{0} 2x:{1} 3x:{2} 4x:{3}".format(*map(len, _resend_log)))

def init_socket():
    global _sock, _sent, _attempts, _cur_seq, _wsize, _sched, _misses
    global _resend_log, _cycle, _created, _is_linked

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
        reset_state()
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
        return -1

    try:
        emit_stream()
    except KeyboardInterrupt:
        print("\n[!] Client manually interrupted.")
        _exit_flag.set()
    except Exception as e:
        print("Emit error:", e)
    finally:
        summarize()
        shutdown()

    return 0

def reconnect():
    global _is_linked
    _is_linked = False
    reset_state()

    while not _is_linked and not _exit_flag.is_set():
        try:
            result = init_socket()
            if result == 0:
                return
            print("Retrying in 10 sec...")
            _exit_flag.wait(timeout=10)
        except KeyboardInterrupt:
            print("\n[!] User interrupted during reconnect.")
            _exit_flag.set()
            break
        except Exception as e:
            print(f"Connection error: {e}")
            _exit_flag.wait(timeout=10)

def emit_stream():
    global _sock, _sent, _attempts, _cur_seq, _wsize, _sched, _misses, _seen
    global _resend_log, _cycle, _created

    print(f"Resuming @ seq: {_cur_seq}, Already sent {_sent}")

    while _sent < PACKET_LIMIT and not _exit_flag.is_set():
        _sched = []
        wait_ack = 0

        for _ in range(_wsize):
            if _created < PACKET_LIMIT:
                if _cur_seq % 1000 == 1 and len(_misses):
                    while len(_sched) <= _wsize and _misses:
                        _sched.append(_misses.popleft())
                    break
                if _cur_seq + PKT_LEN > SEQ_WRAP:
                    _cur_seq = 0
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
                Thread(target=record_miss, args=(item, time.time(), _cycle)).start()
                if _wsize > 1:
                    _wsize = max(1, _wsize // 2)
                    Thread(target=note_window, args=(_wsize, time.time())).start()
            else:
                wait_ack += 1
                try:
                    _sock.sendall((str(item) + " ").encode())
                    _sent += 1
                except Exception as e:
                    print(f"[!] Send failure: {e}")
                    return reconnect()

        _sock.settimeout(0.5)
        try:
            feed = _sock.recv(8192).decode()
            if "FIN" in feed:
                print("[!] Server closed session.")
                break
            confirmations = list(map(int, feed.split()))
        except socket.timeout:
            print("[!] Receive timeout. Reconnecting...")
            return reconnect()
        except Exception as e:
            print("[!] Error receiving: ", e)
            return reconnect()

        for ack in confirmations:
            if ack and _wsize < 2048:
                _wsize += 1
            wait_ack -= 1

        Thread(target=note_window, args=(_wsize, time.time())).start()
        _sock.settimeout(None)

        if _attempts % 100 == 0:
            print(f"[>] Progress: {_sent} packets sent, Window size: {_wsize}")

    summarize()
    shutdown()

if __name__ == '__main__':
    t0 = time.time()
    try:
        reconnect()
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user. Exiting...")
        _exit_flag.set()
    finally:
        summarize()
        shutdown()
        print(f"Elapsed: {time.time() - t0:.2f} sec")
