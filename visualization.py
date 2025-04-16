import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import glob

# Automatically find the latest matching client and server log
client_file = sorted(glob.glob("client_log_*.csv"))[-1]
server_file = sorted(glob.glob("server_log_*.csv"))[-1]

def plot_client_log(filepath):
    df = pd.read_csv(filepath).head(2000)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit='s')

    df["timestamp"] = df["timestamp"] - df["timestamp"].min()
    df["timestamp"] = df["timestamp"].round(0).astype(int)
    
    # Plot drop and retransmit
    drop = df[df["event"] == "drop"]
    retransmit = df[df["event"] == "retransmit"]

    plt.figure()
    plt.scatter(drop["timestamp"], drop["sequence_numbers"].apply(eval).explode(), label="Dropped", color="red", s=10)

    rt_exploded = retransmit.copy()
    rt_exploded["sequence_numbers"] = rt_exploded["sequence_numbers"].apply(eval)
    rt_exploded = rt_exploded.explode("sequence_numbers")

    plt.scatter(rt_exploded["timestamp"], rt_exploded["sequence_numbers"], label="Retransmitted", color="orange", s=10)

    # plt.scatter(retransmit["timestamp"], retransmit["sequence_numbers"].apply(eval).explode(), label="Retransmitted", color="orange", s=10)
    plt.title("Client Packet Drops and Retransmissions")
    plt.xlabel("Time")
    plt.ylabel("Sequence Number")
    plt.legend()
    plt.grid()
    # plt.gca().xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x:.2f}"))
    plt.gca().xaxis.set_major_formatter(ticker.FormatStrFormatter('%d'))
    plt.gca().yaxis.set_major_formatter(ticker.FuncFormatter(lambda y, _: f"{y:.0f}"))
    plt.xticks(rotation=-10)
    plt.savefig("client_packet_events.png")

def plot_server_log(filepath):
    df = pd.read_csv(filepath).head(2000)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit='s')

    df["timestamp"] = df["timestamp"] - df["timestamp"].min()
    df["timestamp"] = df["timestamp"].round(0).astype(int)

    # ACKs over time
    ack_df = df[df["ack"].notna()]

    plt.figure()
    plt.plot(ack_df["timestamp"], ack_df["ack"], label="ACK", color="green")
    plt.title("ACKs Over Time")
    plt.xlabel("Time")
    plt.ylabel("ACK Number")
    plt.grid()
    # plt.gca().xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x:.2f}"))
    plt.gca().yaxis.set_major_formatter(ticker.FuncFormatter(lambda y, _: f"{y:.0f}"))
    plt.gca().xaxis.set_major_formatter(ticker.FormatStrFormatter('%d'))
    plt.xticks(rotation=-10)
    plt.savefig("server_ack_progress.png")

    # Good-put over time
    gp_df = df[df["good_put"].notna()]
    plt.figure()
    plt.plot(gp_df["timestamp"], gp_df["good_put"].astype(float), label="Good-put", color="blue")
    plt.title("Server Good-put Over Time")
    plt.xlabel("Time")
    plt.ylabel("Good-put")
    plt.grid()
    # plt.gca().xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x:.2f}"))
    plt.gca().xaxis.set_major_formatter(ticker.FormatStrFormatter('%d'))
    plt.gca().yaxis.set_major_formatter(ticker.FuncFormatter(lambda y, _: f"{y:.0f}"))
    plt.xticks(rotation=-10)
    plt.savefig("server_goodput.png")

if __name__ == "__main__":
    # plot_client_log("client_log_*.csv")   # replace with actual filename
    # plot_server_log("server_log_*.csv")   # replace with actual filename
    plot_client_log(client_file)
    plot_server_log(server_file)
