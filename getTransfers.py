import ccxt, os, datetime, pandas as pd, pickle
from pathlib import Path
from dotenv import load_dotenv


def get_price_atm():
    # Load .env file
    env_path = Path(".") / ".env"
    load_dotenv(dotenv_path=env_path)
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_SECRET_KEY")
    # Initialize the Binance client
    exchange = ccxt.binance({"apiKey": api_key, "secret": api_secret})

    # get combined_files/combined.csv file to pandas and show available columns
    combined_file = Path("combined_files/combined.csv")
    combined_df = pd.read_csv(combined_file)
    # print(combined_df.columns)
    # show all the unique values under operation, to see what kind of operations are available
    # print(combined_df.Operation.unique())

    # show all deposits
    operations = ["Deposit", "Withdraw"]
    deposits = combined_df[combined_df["Operation"].isin(operations)]

    #    withdrawals = combined_df[combined_df["Operation"] == "Withdraw"]

    # filter out(is not in) usdt, rub, busd
    deposits = deposits[~deposits["Coin"].isin(["USDT", "RUB", "BUSD"])]
    # print(deposits)
    # Change UTC_Time column to the desired datetime format
    deposits["UTC_Time"] = deposits["UTC_Time"].apply(
        lambda x: datetime.datetime.strptime(x, "%Y-%m-%d %H:%M:%S")
    )
    deposits["UTC_Time"] = deposits["UTC_Time"].apply(lambda x: x.date())

    # get price of coin at the time of deposit(UTC_Time column) from Binance using cctx and save to new column Price_ATM
    price_atm_list = []

    for index, row in deposits.iterrows():
        coin_pair = row["Coin"] + "/USDT"
        since_time = (
            int(
                datetime.datetime.combine(
                    row["UTC_Time"], datetime.time.min
                ).timestamp()
            )
            * 1000
        )
        ohlcv_data = exchange.fetch_ohlcv(coin_pair, timeframe="1d", since=since_time)

        if len(ohlcv_data) > 0:
            price_atm = ohlcv_data[0][1]
            price_atm_list.append(price_atm)
        # print(f"Processed row {index}: Coin: {coin_pair}, Price_ATM: {price_atm}")
        else:
            # Handle the case where ohlcv_data is empty
            print(f"No data found for row {index}: Coin: {coin_pair}")

    deposits["Price_ATM"] = price_atm_list
    # save deposits to csv
    deposits.to_csv("deposits.csv", index=False)


# check if deposits.csv exists and load it if not execute the function get_price_atm()
deposits_file = Path("deposits.csv")
if deposits_file.exists():
    deposits = pd.read_csv("deposits.csv")
else:
    get_price_atm()
    deposits = pd.read_csv("deposits.csv")


# sum change for each coin and show it with total spent money sum(price_atm * change)

deposits["Total_Spent"] = deposits["Price_ATM"] * deposits["Change"]
deposits = deposits.groupby(["Operation", "Coin"]).agg(
    {"Change": "sum", "Total_Spent": "sum"}
)
deposits = deposits.sort_values(by="Total_Spent", ascending=False)


print(deposits)
