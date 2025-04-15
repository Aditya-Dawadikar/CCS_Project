import socket
import time
import random

# ANSI escape codes for colorized logs
class LogColor:
    BLUE = '\033[96m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    WHITE = '\033[0m'

SERVER_IP = "127.0.0.1"
PORT = 12345
WINDOW_SIZE = 5
MAX_SEQUENCE = 216
PACKET_COUNT = 10000000
DROP_PROBABILITY = 0.01
MAX_RETRIES = 10

class TCPClient:
    def __init__(self):
        self.client_socket = None
        self.sequence_number = 1
        self.sent_packets = []
        self.acknowledged = set()
        self.dropped_packets = set()

    def connect_to_server(self):
        retry = 0
        while True:
            try:
                print(f"{LogColor.WHITE}[CLIENT] Attempting to connect to server... (Attempt {retry + 1}){LogColor.WHITE}")
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.connect((SERVER_IP, PORT))
                self.client_socket.send("network".encode())
                response = self.client_socket.recv(1024).decode()
                print(f"{LogColor.WHITE}[CLIENT] Server Response: {response}{LogColor.WHITE}")
                return
            except (ConnectionRefusedError, socket.error):
                retry += 1
                backoff = min(2 ** retry, 60)
                print(f"{LogColor.RED}[CLIENT] Connection failed. Retrying in {backoff} seconds...{LogColor.WHITE}")
                time.sleep(backoff)

    def send_packets(self):
        retry = 0
        while True:
            try:
                self.sequence_number = 1
                self.sent_packets.clear()
                self.acknowledged.clear()
                self.dropped_packets.clear()

                while self.sequence_number <= PACKET_COUNT:
                    window = []
                    to_resend = []

                    for _ in range(WINDOW_SIZE):
                        if self.sequence_number > PACKET_COUNT:
                            break

                        if random.random() > DROP_PROBABILITY:
                            if self.sequence_number in self.dropped_packets:
                                to_resend.append(self.sequence_number)
                                self.dropped_packets.discard(self.sequence_number)
                            else:
                                window.append(self.sequence_number)

                            self.sent_packets.append(self.sequence_number)
                        else:
                            self.dropped_packets.add(self.sequence_number)
                            print(f"{LogColor.RED}[DROP] Packet dropped: {self.sequence_number}{LogColor.WHITE}")

                        self.sequence_number = (self.sequence_number % MAX_SEQUENCE) + 1

                    if window:
                        print(f"{LogColor.BLUE}[TX] Sending packet(s): {window}{LogColor.WHITE}")
                        self.client_socket.send(','.join(map(str, window)).encode())

                    if to_resend:
                        print(f"{LogColor.YELLOW}[RTX] Resending packet(s): {to_resend}{LogColor.WHITE}")
                        self.client_socket.send(','.join(map(str, to_resend)).encode())

                    try:
                        ack = int(self.client_socket.recv(1024).decode())
                        print(f"{LogColor.GREEN}[ACK] Received ACK: {ack}{LogColor.WHITE}")
                        self.acknowledged.add(ack)
                    except (ValueError, socket.error):
                        print(f"{LogColor.RED}[ERROR] Failed to receive ACK. Will retry connection...{LogColor.WHITE}")
                        raise ConnectionResetError

                    if self.sequence_number % 100 == 0:
                        missing_packets = set(self.sent_packets) - self.acknowledged
                        retransmit = list(self.dropped_packets & missing_packets)
                        if retransmit:
                            print(f"{LogColor.YELLOW}[RTX] Resending packet(s): {retransmit}{LogColor.WHITE}")
                            self.client_socket.send(','.join(map(str, retransmit)).encode())
                            self.dropped_packets -= set(retransmit)

                    time.sleep(random.uniform(0.2, 0.5))

                self.client_socket.close()
                break  # Done sending all packets

            except (ConnectionResetError, BrokenPipeError, socket.error):
                retry += 1
                backoff = min(2 ** retry, 60)
                print(f"{LogColor.RED}[CLIENT] Connection lost. Retrying in {backoff}s...{LogColor.WHITE}")
                time.sleep(backoff)
                self.connect_to_server()  # reconnect and start fresh


if __name__ == "__main__":
    client = TCPClient()
    try:
        client.connect_to_server()
        client.send_packets()
    except KeyboardInterrupt:
        print(f"\n{LogColor.WHITE}[CLIENT] Interrupted by user. Closing connection.{LogColor.WHITE}")
    except ConnectionError as e:
        print(f"{LogColor.RED}{e}{LogColor.WHITE}")
    finally:
        if client.client_socket:
            client.client_socket.close()
        print(f"{LogColor.WHITE}[CLIENT] Socket closed. Exiting.{LogColor.WHITE}")
