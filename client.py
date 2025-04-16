import socket
import time
import random
import csv
from datetime import datetime
import argparse

class LogColor:
    NEON = '\033[96m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    WHITE = '\033[0m'

SERVER_IP = "127.0.0.1"
PORT = 12345
WINDOW_SIZE = 5
MAX_SEQUENCE = 216
PACKET_COUNT = 10000
DROP_PROBABILITY = 0.04

class TCPClient:
    def __init__(self, enable_logging=False):
        self.client_socket = None
        self.sequence_number = 1
        self.sent_packets = []
        self.acknowledged = set()
        self.dropped_packets = set()
        self.enable_logging = enable_logging

        if self.enable_logging:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.log_file = open(f"client_log_{timestamp}.csv", mode='w', newline='')
            self.logger = csv.writer(self.log_file)
            self.logger.writerow(["timestamp", "event", "sequence_numbers"])
        else:
            self.log_file = None
            self.logger = None

    def connect_to_server(self):
        retry = 0
        while True:
            try:
                print(f"{LogColor.WHITE}[CLIENT] Attempting to connect to server... (Attempt {retry + 1}){LogColor.WHITE}")
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.settimeout(5.0)
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

    def recv_ack(self):
        data = b""
        try:
            while not data.endswith(b"\n"):
                chunk = self.client_socket.recv(1024)
                if not chunk:
                    raise ConnectionResetError("Connection lost while waiting for ACK")
                data += chunk
        except socket.timeout:
            print(f"{LogColor.RED}[CLIENT] Timeout while waiting for ACK{LogColor.WHITE}")
            return None

        decoded = data.decode()
        lines = decoded.split('\n')  # Don't strip before split!

        for line in lines:
            cleaned = line.strip()
            if cleaned.isdigit():
                print(f"{LogColor.WHITE}[CLIENT] Raw ACK received: '{cleaned}'{LogColor.WHITE}")
                return int(cleaned)

        print(f"{LogColor.RED}[CLIENT] Invalid ACK(s) received: {lines}{LogColor.WHITE}")
        return None


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
                            if self.enable_logging and self.logger:
                                self.logger.writerow([time.time(), "drop", [self.sequence_number]])

                        self.sequence_number = (self.sequence_number % MAX_SEQUENCE) + 1

                    if window:
                        print(f"{LogColor.NEON}[TX] Sending packet(s): {window}{LogColor.WHITE}")
                        # self.client_socket.send(','.join(map(str, window)).encode())
                        packet_str = ','.join(map(str, window)) + '\n'
                        self.client_socket.send(packet_str.encode())
                        
                        if self.enable_logging and self.logger:
                            self.logger.writerow([time.time(), "send", window])

                    if to_resend:
                        print(f"{LogColor.YELLOW}[RTX] Resending packet(s): {to_resend}{LogColor.WHITE}")
                        packet_str = ','.join(map(str, to_resend)) + '\n'
                        self.client_socket.send(packet_str.encode())
                        # self.client_socket.send(','.join(map(str, to_resend)).encode())
                        if self.enable_logging and self.logger:
                            self.logger.writerow([time.time(), "retransmit", to_resend])

                    ack = self.recv_ack()
                    if ack is not None:
                        print(f"{LogColor.GREEN}[ACK] Received ACK: {ack}{LogColor.WHITE}")
                        self.acknowledged.add(ack)

                    if self.enable_logging and len(self.sent_packets) % 100 == 0 and self.log_file:
                        self.log_file.flush()

                    if self.sequence_number % 100 == 0:
                        missing_packets = set(self.sent_packets) - self.acknowledged
                        retransmit = list(self.dropped_packets & missing_packets)
                        if retransmit:
                            print(f"{LogColor.YELLOW}[RTX] Resending packet(s): {retransmit}{LogColor.WHITE}")

                            payload = ','.join(map(str, retransmit)) + '\n'
                            self.client_socket.send(payload.encode())

                            # self.client_socket.send(','.join(map(str, retransmit)).encode())
                            if self.enable_logging and self.logger:
                                self.logger.writerow([time.time(), "retransmit", retransmit])
                            self.dropped_packets -= set(retransmit)

                self.client_socket.send("TERMINATE\n".encode())
                print(f"{LogColor.WHITE}[CLIENT] Sent TERMINATE signal to server.{LogColor.WHITE}")
                self.client_socket.close()
                break

            except (ConnectionResetError, BrokenPipeError, socket.error) as e:
                retry += 1
                backoff = min(2 ** retry, 60)
                print(f"{LogColor.RED}[CLIENT] Connection error: {e}. Retrying in {backoff}s...{LogColor.WHITE}")
                time.sleep(backoff)
                self.connect_to_server()

    def close(self):
        if self.log_file:
            self.log_file.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", action="store_true", help="Enable CSV logging")
    args = parser.parse_args()

    client = TCPClient(enable_logging=args.log)
    try:
        client.connect_to_server()
        client.send_packets()
    except KeyboardInterrupt:
        print(f"\n{LogColor.WHITE}[CLIENT] Interrupted by user. Closing connection.{LogColor.WHITE}")
    finally:
        if client.client_socket:
            client.client_socket.close()
        client.close()
        print(f"{LogColor.WHITE}[CLIENT] Socket closed. Exiting.{LogColor.WHITE}")
