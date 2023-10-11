from pathlib import Path
from dotenv import load_dotenv
import ccxt, pickle, time, pandas as pd, os, datetime
from tokens import COIN_IDS

# Load .env file
env_path = Path(".") / ".env"
load_dotenv(dotenv_path=env_path)

api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_SECRET_KEY")

# Initialize the Binance client
exchange = ccxt.binance({"apiKey": api_key, "secret": api_secret})
# Initialize an empty list to store invalid symbols
invalid_symbols = []

# Load invalid symbols from a file if it exists
invalid_symbols_file = Path("invalid_symbols.pkl")
if invalid_symbols_file.exists():
    with open("invalid_symbols.pkl", "rb") as file:
        invalid_symbols = pickle.load(file)


# # Convert coin IDs to symbols
# symbols = [coin.upper() + "/USDT" for coin in COIN_IDS.keys()] + [
#     coin.upper() + "/BUSD" for coin in COIN_IDS.keys()
# ]

# Fetch account balance
all_balance = exchange.fetch_balance()
balance = {
    currency: value for currency, value in all_balance["total"].items() if value > 0
}
# Convert the start date to a timestamp in milliseconds
start_date = "2020-12-01"
start_timestamp = int(
    datetime.datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000
)
print(balance.keys())
# List of currencies to fetch trades for
currencies = list(balance.keys())
# manual_currencies = ["BTC", "ETH", "ADA"]  # replace with your list of currencies
# currencies.extend(manual_currencies)
currencies = list(set(currencies))  # remove duplicates


# Check if the CSV file with trades exists and load it
csv_file = Path("all_trades.csv")
if csv_file.exists():
    try:
        all_trades = pd.read_csv("all_trades.csv")
        last_timestamp = max(all_trades["timestamp"].max(), start_timestamp)
    except:
        all_trades = pd.DataFrame()
        last_timestamp = start_timestamp
else:
    # If file does not exist, create an empty DataFrame and set last_timestamp to 0
    all_trades = pd.DataFrame()
    last_timestamp = start_timestamp

# Fetch trades for each currency
for currency in currencies:
    # Determine the start timestamp for this currency
    currency_trades = all_trades[all_trades["symbol"] == f"{currency}/USDT"]
    if not currency_trades.empty:
        last_timestamp = currency_trades["timestamp"].max()
    else:
        last_timestamp = start_timestamp

    # Fetch trades
    try:
        trades = exchange.fetchMyTrades(f"{currency}/USDT", since=last_timestamp)
        df = pd.DataFrame(trades)
        all_trades = pd.concat([all_trades, df])
    except Exception as e:
        print(f"Cannot fetch trades for symbol {currency}/USDT: {str(e)}")

    # Wait for 1 second to avoid hitting rate limits
    time.sleep(1)

# Remove duplicates
all_trades.drop_duplicates(subset="datetime", keep="first", inplace=True)


all_trades.to_csv("all_trades.csv", index=False)

# Print information about collected data
print(f"Number of records: {len(all_trades)}")
if not all_trades.empty:
    print(f"Earliest timestamp: {all_trades['timestamp'].min()}")
    print(f"Latest timestamp: {all_trades['timestamp'].max()}")
