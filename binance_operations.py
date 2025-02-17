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
        
        # Setup cache directories
        self.cache_dir = Path("Cache")
        self.data_dir = Path("Data")
        self.cache_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)
        
        # Load pairs to skip
        self.pairs_to_skip = self.load_ignore_list()
        
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
        trades_file = self.data_dir / "all_trades.csv"
        if trades_file.exists():
            try:
                all_trades = pd.read_csv(trades_file)
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
        trades_file.parent.mkdir(exist_ok=True)
        all_trades.to_csv(trades_file, index=False)

        return all_trades

    def get_trades_analysis_data(self):
        """Get current balance and trades data for analysis"""
        total_balance = self.exchange.fetch_balance()["total"]
        trades_file = self.data_dir / "all_trades.csv"
        trades_df = pd.read_csv(trades_file)
        trades_df["symbol"] = trades_df["symbol"].str.replace("BUSD", "USDT")
        
        return trades_df, total_balance

    def additional_purchase(self, Q1, P1, P2):
        """Calculate additional purchase amount for averaging strategy"""
        return Q1 * (P1 - P2) / (P2 - (P1 + P2) / 2)

    def load_ignore_list(self):
        """Load list of pairs to ignore from JSON file"""
        try:
            ignore_file = self.cache_dir / "pair_skip.json"
            if not ignore_file.exists():
                # Create initial empty ignore list
                self.save_ignore_list([])
                return []
            
            with open(ignore_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading ignore list: {e}")
            return []

    def save_ignore_list(self, pairs):
        """Save ignore list to JSON file"""
        try:
            ignore_file = self.cache_dir / "pair_skip.json"
            self.cache_dir.mkdir(exist_ok=True)
            with open(ignore_file, 'w') as f:
                json.dump(pairs, f, indent=4)
        except Exception as e:
            print(f"Error saving ignore list: {e}")

    def add_to_ignore_list(self, pair):
        """Add a trading pair to the ignore list"""
        pairs = self.load_ignore_list()
        
        # Standardize pair format
        pair = pair.upper()
        
        if pair not in pairs:
            pairs.append(pair)
            self.save_ignore_list(pairs)
            print(f"Added {pair} to ignore list")
            # Update current pairs_to_skip
            self.pairs_to_skip = pairs
        else:
            print(f"{pair} is already in ignore list")
        
        # Show current ignore list
        print("\nCurrent ignore list:")
        for p in sorted(pairs):
            print(f"- {p}") 