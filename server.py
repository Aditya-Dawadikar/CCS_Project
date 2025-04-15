import socket
import threading
import time

# ANSI escape codes for colorized logs
class LogColor:
    BLUE = '\033[96m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    WHITE = '\033[0m'

HOST = '0.0.0.0'
PORT = 12345
BUFFER_SIZE = 1024

class TCPServer:
    def __init__(self):
        self.lock = threading.Lock()
        self.active_clients = 0
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((HOST, PORT))
        self.server_socket.listen(5)
        self.server_socket.settimeout(5.0)  # heartbeat timer
        print(f"{LogColor.WHITE}[SERVER] Listening on port {PORT}{LogColor.WHITE}")

    def handle_client(self, conn, addr):
        client_id = f"{addr[0]}:{addr[1]}"
        print(f"\n{LogColor.WHITE}[CLIENT {client_id}] --- New session started ---{LogColor.WHITE}")
        
        with self.lock:
            self.active_clients += 1

        recv_packets = set()
        tot_recv = 0
        tot_miss = 0

        try:
            initial_msg = conn.recv(BUFFER_SIZE).decode()
            if initial_msg:
                print(f"{LogColor.WHITE}[CLIENT {client_id}] Received handshake: {initial_msg}{LogColor.WHITE}")
                conn.send("success".encode())

            while True:
                data = conn.recv(BUFFER_SIZE).decode()
                if not data:
                    break

                seq_numbers = list(map(int, data.split(',')))
                print(f"{LogColor.BLUE}[CLIENT {client_id}] Received packet(s): {seq_numbers}{LogColor.WHITE}")

                with self.lock:
                    for seq in seq_numbers:
                        recv_packets.add(seq)
                        tot_recv += 1

                    max_received = max(recv_packets)
                    missing_packets = set(range(1, max_received + 1)) - recv_packets
                    tot_miss = len(missing_packets)

                    if missing_packets:
                        print(f"{LogColor.YELLOW}[CLIENT {client_id}] Missing packets (so far): {sorted(missing_packets)}{LogColor.WHITE}")

                    last_ack = max(seq_numbers)
                    conn.send(str(last_ack).encode())
                    print(f"{LogColor.GREEN}[CLIENT {client_id}] Sent ACK: {last_ack}{LogColor.WHITE}")

                    if tot_recv % 1000 == 0:
                        good_put = (tot_recv - tot_miss) / tot_recv
                        print(f"{LogColor.WHITE}[CLIENT {client_id}] Good-put: {good_put:.4f}{LogColor.WHITE}")

        except (ConnectionResetError, BrokenPipeError) as e:
            print(f"{LogColor.RED}[CLIENT {client_id}] Connection lost: {e}{LogColor.WHITE}")
        except Exception as e:
            print(f"{LogColor.RED}[CLIENT {client_id}] Error: {e}{LogColor.WHITE}")
        finally:
            conn.close()
            print(f"{LogColor.WHITE}[CLIENT {client_id}] Connection closed.{LogColor.WHITE}")
            with self.lock:
                self.active_clients -= 1

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

# Start Server
if __name__ == "__main__":
    server = TCPServer()
    server.start_server()
