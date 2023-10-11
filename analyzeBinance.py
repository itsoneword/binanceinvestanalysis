import os, pickle, ccxt, pandas as pd, json
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(".") / ".env"
load_dotenv(dotenv_path=env_path)

api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_SECRET_KEY")

# Load the CSV file into a DataFrame
trades_df = pd.read_csv("all_trades.csv")

# Initialize the Binance client
exchange = ccxt.binance({"apiKey": api_key, "secret": api_secret})
with open("pair_skip.json", "r") as file:
    pairs_to_skip = json.load(file)


def get_current_balance(df, actual_token_balance):
    # Calculate the current balance for each coin by subtracting the total sell amount from the total buy amount
    balance = (
        df[df["side"] == "buy"]["amount"].sum()
        - df[df["side"] == "sell"]["amount"].sum()
    )
    if (
        balance < (df[df["side"] == "buy"]["amount"].sum() * 0.05)
        and actual_token_balance == 0
    ):
        balance = actual_token_balance

    if actual_token_balance > balance:
        balance = actual_token_balance
    return balance


def get_current_price(symbol, prices_dict):
    # Check if the price is in the prices dictionary
    if symbol in prices_dict:
        # Check if the price data is in the old format
        if isinstance(prices_dict[symbol], float):
            # Convert the old format to the new format
            prices_dict[symbol] = {
                "price": prices_dict[symbol],
                "timestamp": datetime.now(),
            }
            print(f"Converted price data for {symbol} to new format")

        print(f"Current timestamp for {symbol}: {prices_dict[symbol]['timestamp']}")
        print(f"Current time: {datetime.now()}")
        print(f"Time difference: {datetime.now() - prices_dict[symbol]['timestamp']}")

        # Check if the price data is more than an hour old
        if prices_dict[symbol]["timestamp"] < datetime.now() - timedelta(minutes=60):
            print(
                f"{symbol} price in cache is outdated, getting new price from Binance API"
            )
            try:
                ticker = exchange.fetch_ticker(symbol.replace("/", ""))
                current_price = ticker["last"]
                # Update the price and timestamp in the prices dictionary
                prices_dict[symbol] = {
                    "price": current_price,
                    "timestamp": datetime.now(),
                }
                # Save the updated prices dictionary to a pickle file
                with open("prices.pkl", "wb") as f:
                    pickle.dump(prices_dict, f)
            except:
                print(f"{symbol} pair does not exist on Binance")
                current_price = 1
        else:
            # If the price data in the cache is up-to-date, use it
            current_price = prices_dict[symbol]["price"]
    else:
        print(f"{symbol} not in cache, getting price from Binance API")
        try:
            ticker = exchange.fetch_ticker(symbol.replace("/", ""))
            current_price = ticker["last"]
            # Add the price and timestamp to the prices dictionary
            prices_dict[symbol] = {"price": current_price, "timestamp": datetime.now()}
            # Save the prices dictionary to a pickle file
            with open("prices.pkl", "wb") as f:
                pickle.dump(prices_dict, f)
        except:
            print(f"{symbol} pair does not exist on Binance")
            current_price = 1
    return current_price


# def fetch_price(symbol, prices_dict):
#     try:
#         ticker = exchange.fetch_ticker(symbol.replace("/", ""))
#         current_price = ticker["last"]
#         # Add the price and timestamp to the prices dictionary
#         prices_dict[symbol] = {"price": current_price, "timestamp": datetime.now()}
#         # Save the prices dictionary to a pickle file
#         with open("prices.pkl", "wb") as f:
#             pickle.dump(prices_dict, f)
#     except:
#         print(symbol, "pair does not exist on Binance")
#         current_price = 1
#     return current_price


# Load the prices pickle file into a dictionary if it exists, otherwise create a new dictionary
prices_file = Path("prices.pkl")
if prices_file.exists():
    with open("prices.pkl", "rb") as f:
        prices_dict = pickle.load(f)
else:
    prices_dict = {}

# Create a new DataFrame to store the output
output_df = output_df_sold = pd.DataFrame(
    columns=[
        "Symbol",
        "# Trades",
        "USD spent",
        "USD Value",
        "p\l",
        "AvPr",
        "CrPr",
        "Diff",
        "Buy extra USD",
        "Expected t",
        "Available t",
        "USD Sell",
    ]
)

total_balance = exchange.fetch_balance()["total"]

# Group the DataFrame by symbol
trades_df["symbol"] = trades_df["symbol"].str.replace("BUSD", "USDT")

grouped = trades_df.groupby("symbol")


def additional_purchase(Q1, P1, P2):
    return Q1 * (P1 - P2) / (P2 - (P1 + P2) / 2)


# Calculate the requested information for each coin
for symbol, group in grouped:
    if symbol in pairs_to_skip:
        continue
    num_trades = len(group)
    usd_spent_buy = group[group["side"] == "buy"]["cost"].sum()
    bought_tokens = group[group["side"] == "buy"]["amount"].sum()
    usd_spent_sell = group[group["side"] == "sell"]["cost"].sum()
    coin_symbol = symbol.split("/")[0]
    actual_token_balance = total_balance.get(coin_symbol, 0)
    current_balance = get_current_balance(group, actual_token_balance)
    current_price = get_current_price(symbol, prices_dict)
    current_usd_value = current_balance * current_price
    # Extract the coin symbol from the trading pair and get the actual token balance
    if current_balance > 0 and (usd_spent_buy - usd_spent_sell) > 0:
        avpr = (usd_spent_buy - usd_spent_sell) / current_balance
    elif usd_spent_buy > 0:
        avpr = usd_spent_buy / bought_tokens
    else:
        avpr = current_price

    pricedf = int(((current_price - avpr) / avpr) * 100)
    adpch = (
        (
            additional_purchase(current_balance, avpr, current_price)
            * current_price
            * -1
        ).astype(int)
        if pricedf < 0
        else -1
    )
    # Add the data to the output DataFrame
    # With these lines:
    if current_balance > 0:
        new_row = pd.DataFrame(
            [
                {
                    "Symbol": symbol,
                    "# Trades": num_trades,
                    "USD spent": usd_spent_buy - usd_spent_sell,
                    "USD Value": current_usd_value,
                    "p\l": (usd_spent_buy - usd_spent_sell - current_usd_value),
                    "AvPr": avpr,
                    "CrPr": current_price,
                    "Diff": pricedf,
                    "Buy extra USD": adpch,
                    "Expected t": current_balance,
                    "Available t": actual_token_balance,
                    "USD Sell": usd_spent_sell,
                }
            ]
        )
        output_df = pd.concat([output_df, new_row], ignore_index=True)
    else:
        new_row_sold = pd.DataFrame(
            [
                {
                    "Symbol": symbol,
                    "# Trades": num_trades,
                    "USD spent": usd_spent_buy,
                    "USD Value": current_usd_value,
                    "p\l": (usd_spent_buy - usd_spent_sell - current_usd_value),
                    "AvPr": avpr,
                    "CrPr": current_price,
                    "Diff": pricedf,
                    "Buy extra USD": adpch,
                    "Expected t": current_balance,
                    "Available t": actual_token_balance,
                    "USD Sell": usd_spent_sell,
                }
            ]
        )
        output_df_sold = pd.concat([output_df_sold, new_row_sold], ignore_index=True)
output_df = output_df.sort_values("USD Value", ascending=False)

output_df = pd.concat([output_df, output_df_sold], ignore_index=True)
# Calculate the sums
total_buy = output_df["USD spent"].sum()
total_sell = output_df["USD Sell"].sum()
total_pl = output_df["p\\l"].sum()

# Create a new DataFrame with the sums
sums_df = pd.DataFrame(
    [
        {
            "Symbol": "TOTAL",
            "USD spent": total_buy,
            "USD Sell": total_sell,
            "p\\l": total_pl,
        }
    ]
)

# Append the sums DataFrame to the output DataFrame
output_df = pd.concat([output_df, sums_df], ignore_index=True)

# Display the output DataFrame
pd.set_option("display.float_format", "{:.5f}".format)

output_filename = "binance_api_analysis.csv"
backup_folder = "backfiles"
# Check if the output file already exists
if os.path.exists(output_filename):
    # Get the current datetime
    current_datetime = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Create a backup folder if it doesn't exist
    if not os.path.exists(backup_folder):
        os.makedirs(backup_folder)

    # Generate the backup filename
    backup_filename = os.path.join(
        backup_folder, f"{current_datetime}_{output_filename}"
    )

    # Move the existing file to the backup location
    os.rename(output_filename, backup_filename)
    print(f"Backup created: {backup_filename}")

output_df.to_csv(output_filename, index=False)


print(output_df)
