import socket
import threading
import time
import csv
from datetime import datetime
import argparse

class LogColor:
    BLUE = '\033[96m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    WHITE = '\033[0m'

HOST = '0.0.0.0'
PORT = 12345
BUFFER_SIZE = 1024
GOODPUT_EVERY_N_PACKETS = 40

class TCPServer:
    def __init__(self, enable_logging=False):
        self.lock = threading.Lock()
        self.active_clients = 0
        self.enable_logging = enable_logging
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((HOST, PORT))
        self.server_socket.listen(5)
        self.server_socket.settimeout(5.0)
        print(f"{LogColor.WHITE}[SERVER] Listening on port {PORT}{LogColor.WHITE}")

    def handle_client(self, conn, addr):
        client_id = f"{addr[0]}_{addr[1]}"
        print(f"\n{LogColor.WHITE}[CLIENT {client_id}] --- New session started ---{LogColor.WHITE}")

        with self.lock:
            self.active_clients += 1

        recv_packets = set()
        tot_recv = 0
        tot_miss = 0
        recent_recv_count = 0
        recent_miss_count = 0

        if self.enable_logging:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = open(f"server_log_{client_id}_{timestamp}.csv", mode='w', newline='')
            logger = csv.writer(log_file)
            logger.writerow(["timestamp", "event", "sequence_numbers", "ack", "good_put"])
        else:
            logger = None

        try:
            initial_msg = conn.recv(BUFFER_SIZE).decode()
            if initial_msg:
                print(f"{LogColor.WHITE}[CLIENT {client_id}] Received handshake: {initial_msg}{LogColor.WHITE}")
                conn.send("success".encode())

            buffer = ""
            while True:
                chunk = conn.recv(BUFFER_SIZE).decode()
                if not chunk:
                    break

                buffer += chunk

                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.strip()

                    if line == "TERMINATE":
                        print(f"{LogColor.WHITE}[CLIENT {client_id}] Termination signal received. Closing session.{LogColor.WHITE}")
                        return

                    raw_items = line.split(',')
                    seq_numbers = []
                    bad_entries = []

                    for item in raw_items:
                        cleaned = item.strip()
                        if cleaned.isdigit():
                            seq_numbers.append(int(cleaned))
                        elif cleaned != "":
                            bad_entries.append(item)

                    print("-------------------------------------------")
                    print("received data: ", seq_numbers)
                    print("-------------------------------------------")

                    if bad_entries:
                        print(f"{LogColor.RED}[CLIENT {client_id}] ⚠️ Ignored malformed packets: {bad_entries}{LogColor.WHITE}")

                    if not seq_numbers:
                        continue

                    print(f"{LogColor.BLUE}[CLIENT {client_id}] Received packet(s): {seq_numbers}{LogColor.WHITE}")
                    if logger:
                        logger.writerow([time.time(), "receive", seq_numbers, "", ""])

                    with self.lock:
                        for seq in seq_numbers:
                            recv_packets.add(seq)
                            tot_recv += 1

                        max_received = max(recv_packets)
                        missing_packets = set(range(1, max_received + 1)) - recv_packets
                        tot_miss = len(missing_packets)

                        if missing_packets and tot_recv % 1000 == 0:
                            print(f"{LogColor.YELLOW}[CLIENT {client_id}] Missing packets: {len(missing_packets)} total, last missing: {max(missing_packets)}{LogColor.WHITE}")

                        last_ack = max(seq_numbers)
                        conn.send(f"{last_ack}\n".encode())
                        print(f"{LogColor.GREEN}[CLIENT {client_id}] Sent ACK: {last_ack}{LogColor.WHITE}")
                        if logger:
                            logger.writerow([time.time(), "ack", "", last_ack, ""])

                        # Sliding window goodput logic
                        recent_recv_count += len(seq_numbers)
                        batch_max = max(seq_numbers)
                        batch_expected = set(range(min(seq_numbers), batch_max + 1))
                        batch_missing = batch_expected - set(seq_numbers)
                        recent_miss_count += len(batch_missing)

                        if recent_recv_count >= GOODPUT_EVERY_N_PACKETS:
                            good_put = (recent_recv_count - recent_miss_count) / recent_recv_count
                            print(f"{LogColor.WHITE}[CLIENT {client_id}] Good-put (last {recent_recv_count}): {good_put:.4f}{LogColor.WHITE}")
                            if logger:
                                logger.writerow([time.time(), "goodput", "", "", f"{good_put:.4f}"])
                            recent_recv_count = 0
                            recent_miss_count = 0

                        if self.enable_logging and tot_recv % 100 == 0 and logger:
                            log_file.flush()

        except Exception as e:
            print(f"{LogColor.RED}[CLIENT {client_id}] Error: {e}{LogColor.WHITE}")
        finally:
            conn.close()
            if logger:
                log_file.close()
            with self.lock:
                self.active_clients -= 1
            print(f"{LogColor.WHITE}[CLIENT {client_id}] Connection closed.{LogColor.WHITE}")

    def start_server(self):
        try:
            while True:
                try:
                    conn, addr = self.server_socket.accept()
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(conn, addr),
                        daemon=True
                    )
                    client_thread.start()
                except socket.timeout:
                    with self.lock:
                        if self.active_clients == 0:
                            print(f"{LogColor.WHITE}[SERVER] Waiting for connections...{LogColor.WHITE}")
        except KeyboardInterrupt:
            print(f"\n{LogColor.WHITE}[SERVER] Interrupted by user. Shutting down...{LogColor.WHITE}")
        finally:
            self.server_socket.close()
            print(f"{LogColor.WHITE}[SERVER] Socket closed. Server exited.{LogColor.WHITE}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", action="store_true", help="Enable CSV logging")
    args = parser.parse_args()

    server = TCPServer(enable_logging=args.log)
    server.start_server()
