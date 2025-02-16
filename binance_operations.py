import ccxt
import pandas as pd
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import os
import json
import time

class BinanceOperations:
    def __init__(self):
        # Load credentials
        env_path = Path(".") / ".env"
        load_dotenv(dotenv_path=env_path)
        self.api_key = os.getenv("BINANCE_API_KEY")
        self.api_secret = os.getenv("BINANCE_SECRET_KEY")
        self.exchange = ccxt.binance({"apiKey": self.api_key, "secret": self.api_secret})
        
        # Load pairs to skip
        with open('Data/pair_skip.json', 'r') as file:
            self.pairs_to_skip = json.load(file)
        
    def get_account_balance(self):
        """Get current account balance"""
        all_balance = self.exchange.fetch_balance()
        return {currency: value for currency, value in all_balance["total"].items() if value > 0}

    def get_current_balance(self, df, actual_token_balance):
        """Calculate the current balance for each coin"""
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

    def fetch_all_trades(self, start_date="2020-12-01"):
        """Fetch all trades from Binance"""
        start_timestamp = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
        balance = self.get_account_balance()
        currencies = list(set(balance.keys()))

        # Check if existing trades file exists
        csv_file = Path("Data/all_trades.csv")
        if csv_file.exists():
            try:
                all_trades = pd.read_csv(csv_file)
                last_timestamp = max(all_trades["timestamp"].max(), start_timestamp)
            except:
                all_trades = pd.DataFrame()
                last_timestamp = start_timestamp
        else:
            all_trades = pd.DataFrame()
            last_timestamp = start_timestamp

        # Fetch trades for each currency
        for currency in currencies:
            pair = f"{currency}/USDT"
            if pair in self.pairs_to_skip:
                continue

            # Determine start timestamp for this currency
            currency_trades = all_trades[all_trades["symbol"] == pair]
            if not currency_trades.empty:
                last_timestamp = currency_trades["timestamp"].max()
            else:
                last_timestamp = start_timestamp
            
            # Fetch trades
            try:
                trades = self.exchange.fetchMyTrades(pair, since=last_timestamp)
                df = pd.DataFrame(trades)
                all_trades = pd.concat([all_trades, df])
            except Exception as e:
                print(f"Cannot fetch trades for symbol {pair}: {str(e)}")

            time.sleep(0.3)  # Rate limiting

        # Clean up and save trades
        if 'info' in all_trades.columns:
            all_trades.drop(columns=["info"], inplace=True)
        all_trades.drop_duplicates(subset="datetime", keep="first", inplace=True)
        all_trades.to_csv("Data/all_trades.csv", index=False)

        return all_trades

    def get_trades_analysis_data(self):
        """Get current balance and trades data for analysis"""
        total_balance = self.exchange.fetch_balance()["total"]
        trades_df = pd.read_csv("./Data/all_trades.csv")
        trades_df["symbol"] = trades_df["symbol"].str.replace("BUSD", "USDT")
        
        return trades_df, total_balance

    def additional_purchase(self, Q1, P1, P2):
        """Calculate additional purchase amount for averaging strategy"""
        return Q1 * (P1 - P2) / (P2 - (P1 + P2) / 2) 