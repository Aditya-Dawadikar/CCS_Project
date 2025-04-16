import socket
from threading import Thread, Lock
import time

ACK_COUNT = 0
TOTAL = 10_000_000
CUR_SEQ = 0
CHUNK = 4
LIMIT = 65536
EXPECT = 1
LAGGED = []
OBSERVED = []
YIELD = []
POOL = []
SEQ_BATCH = []
_frag = ''
B_WIDTH = 8192
MIN_W = 1024
MAX_W = 32768
CID = ''
INIT_TIME = time.time()

sink_seq = open(f"rx_{int(time.time())}.csv", "w")
sink_seq.write("seq,time\n")
sink_eff = open(f"efficiency_{int(time.time())}.csv", "w")
sink_eff.write("received,sent,eff\n")

report_lock = Lock()
sink_flow = open(f"recv_winsz_{int(time.time())}.csv", "w")
sink_flow.write("recv_win,timestamp\n")
flow_lock = Lock()

def launch():
    global listener, target
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    target = socket.gethostname()
    port = 4001

    try:
        listener.bind((target, port))
    except Exception as e:
        print("BindFail:", str(e))

    print("Awaiting peer...")
    listener.listen(5)
    print("Listening @", target, ":", port)

def handshake():
    global conn, listener, ACK_COUNT, CUR_SEQ, EXPECT, LAGGED, OBSERVED, YIELD, SEQ_BATCH, _frag, B_WIDTH, CID, INIT_TIME

    if ACK_COUNT + (TOTAL//100) > TOTAL:
        ACK_COUNT = TOTAL
        final_stats()
        return

    conn, addr = listener.accept()
    INIT_TIME = time.time()
    print("Peer Connected:", addr)
    hello = conn.recv(2048).decode()

    if hello.startswith("SYN"):
        if ACK_COUNT < 10 or CID != hello[4:] or ACK_COUNT > TOTAL * 0.99:
            conn.sendall("NEW".encode())
            CID = hello[4:]
            reset_env()
        else:
            conn.sendall("OLD".encode())
            wait = conn.recv(2048).decode()
            if wait.startswith("SND"):
                dump = f'{{"pkt_rec_cnt": int({ACK_COUNT}), "seq_num": int({CUR_SEQ})}}'
                conn.sendall(dump.encode())

    elif hello.startswith("RCN"):
        conn.sendall("SND".encode())
        CID = hello[4:]
        print("Rebuilding session...")
        dump = conn.recv(4096).decode()
        if dump:
            data = eval(dump)
            ACK_COUNT = data['pkt_success_sent']
            CUR_SEQ = data['seq_num']
            EXPECT = CUR_SEQ + CHUNK
        else:
            print("Failed Sync!")
    else:
        print("Broken handshake")
        exit()

    try:
        stream()
    except Exception as e:
        print(e)

def log_stats(pkts, missed):
    global sink_seq, sink_eff, report_lock, YIELD

    with report_lock:
        for s, t in pkts:
            sink_seq.write(f"{s},{t}\n")

        got = len(pkts)
        sent = got + len(LAGGED)
        ratio = got / sent if sent else 0

        YIELD.append(ratio)
        sink_eff.write(f"{got},{sent},{ratio}\n")

def monitor_flow(size, stamp):
    with flow_lock:
        sink_flow.write(f"{size},{stamp}\n")

def stream():
    global conn, ACK_COUNT, CUR_SEQ, EXPECT, LAGGED, OBSERVED, YIELD, SEQ_BATCH, _frag, B_WIDTH, INIT_TIME

    while ACK_COUNT < TOTAL:
        try:
            conn.settimeout(1)
            res = conn.recv(B_WIDTH).decode()
            conn.settimeout(None)
        except:
            return handshake()

        if not res:
            return handshake()

        parts = res.split()
        SEQ_BATCH = list(map(int, parts))

        if _frag:
            if SEQ_BATCH:
                SEQ_BATCH[0] = int(_frag + parts[0])
            else:
                SEQ_BATCH = list(map(int, _frag.split()))
            _frag = ''

        if not res.endswith(" "):
            SEQ_BATCH.pop()
            _frag += parts.pop()

        flow_scaled = False
        flow_shrink = False

        for sid in SEQ_BATCH:
            outdated = False
            if sid != EXPECT:
                if sid in LAGGED:
                    outdated = True
                    LAGGED.remove(sid)
                else:
                    if not flow_scaled and B_WIDTH * 2 <= MAX_W:
                        flow_scaled = True
                        B_WIDTH *= 2
                        Thread(target=monitor_flow, args=(B_WIDTH, time.time())).start()

                    wait_gap = 0
                    while EXPECT != sid:
                        if wait_gap > 5:
                            break
                        wait_gap += 1
                        LAGGED.append(EXPECT)
                        EXPECT += CHUNK
                        if EXPECT > LIMIT:
                            EXPECT = 1

            elif not (flow_scaled or flow_shrink) and B_WIDTH // 2 >= MIN_W:
                flow_shrink = True
                B_WIDTH //= 2
                Thread(target=monitor_flow, args=(B_WIDTH, time.time())).start()

            if not outdated:
                EXPECT += CHUNK
                if EXPECT > LIMIT:
                    EXPECT = 1

            OBSERVED.append((sid, time.time()))
            ACK_COUNT += 1
            conn.sendall((str(EXPECT) + " ").encode())

            if len(OBSERVED) == 1000:
                Thread(target=log_stats, args=(OBSERVED, len(LAGGED))).start()
                OBSERVED = []

        if ACK_COUNT % 100 == 0:
            print(f"Received: {ACK_COUNT}")
            if ACK_COUNT % 1000 == 0:
                print("Uptime:", time.time() - INIT_TIME)

    final_stats()
    tidy()

def reset_env():
    global ACK_COUNT, CUR_SEQ, EXPECT, LAGGED, OBSERVED, YIELD, SEQ_BATCH, _frag, B_WIDTH
    ACK_COUNT = 0
    CUR_SEQ = 0
    EXPECT = 1
    LAGGED = []
    OBSERVED = []
    YIELD = []
    SEQ_BATCH = []
    _frag = ''
    B_WIDTH = 8192

def final_stats():
    print("All packets processed")
    print(f"Server: {socket.gethostbyname(socket.gethostname())}")
    print(f"Total Received: {ACK_COUNT}")
    if YIELD:
        print(f"Mean Efficiency: {sum(YIELD)/len(YIELD)}")

def tidy():
    time.sleep(1)
    sink_seq.close()
    sink_eff.close()
    conn.close()
    sink_flow.close()

if __name__ == '__main__':
    launch()
    handshake()
    print("Duration:", time.time() - INIT_TIME)
