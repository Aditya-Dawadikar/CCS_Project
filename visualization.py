import pandas as pd
import matplotlib.pyplot as plt

# === Load CSV files ===
sender_window_df = pd.read_csv("winlog_1744785101.csv")
receiver_window_df = pd.read_csv("recv_winsz_1744785108.csv")
received_seq_df = pd.read_csv("rx_1744785108.csv")
dropped_seq_df = pd.read_csv("drops_1744785101.csv")

# === Trim to first 1000 points ===
sender_sample = sender_window_df.head(1000)
receiver_sample = receiver_window_df.head(1000)
received_sample = received_seq_df.head(1000)
dropped_sample = dropped_seq_df.head(1000)

# === Zoomed Plot 1: Window Size ===
plt.figure()
plt.plot(sender_sample["tstamp"], sender_sample["wsize"], label="Sender Window Size")
plt.plot(receiver_sample["timestamp"], receiver_sample["recv_win"], label="Receiver Window Size")
plt.xlabel("Time")
plt.ylabel("Window Size")
plt.title("Window Size Over Time (Zoomed In: First 1000 Points)")
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig("zoom_window_sizes.png")
plt.close()

# === Zoomed Plot 2: Received Sequence Numbers ===
plt.figure()
plt.plot(received_sample["time"], received_sample["seq"])
plt.xlabel("Time")
plt.ylabel("Sequence Number")
plt.title("Received Sequence Numbers (Zoomed In: First 1000 Points)")
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig("zoom_seq_received.png")
plt.close()

# === Zoomed Plot 3: Dropped Sequence Numbers ===
plt.figure()
plt.plot(dropped_sample["tstamp"], dropped_sample["sid"], color='red')
plt.xlabel("Time")
plt.ylabel("Sequence Number")
plt.title("Dropped Sequence Numbers (Zoomed In: First 1000 Points)")
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig("zoom_seq_dropped.png")
plt.close()
