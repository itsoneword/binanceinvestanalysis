from pycoingecko import CoinGeckoAPI
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import time
import os
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class ExternalServices:
    def __init__(self):
        # Initialize CoinGecko
        self.cg = CoinGeckoAPI()
        # Update cache path to use Cache folder
        self.cache_dir = Path("Cache")
        self.cache_file = self.cache_dir / "coingecko_cache.json"
        self.max_cache_hours = 2
        
        # Ensure Cache directory exists
        self.cache_dir.mkdir(exist_ok=True)
        
        # Load token mappings
        self.coin_ids = self.load_token_mappings()
        
        # Setup Google credentials
        self.setup_google_credentials()
        
    def setup_google_credentials(self):
        """Setup Google Sheets credentials"""
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        self.creds = ServiceAccountCredentials.from_json_keyfile_name(
            "./GoogleAcc/creds.json", scope
        )
        self.client = gspread.authorize(self.creds)
        
    def load_token_mappings(self):
        """Load token ID mappings"""
        try:
            if not os.path.exists("tokens.py"):
                # Create initial tokens.py with empty dictionary
                with open("tokens.py", "w") as f:
                    f.write("COIN_IDS = {\n}\n")
                return {}
            
            with open("tokens.py", "r") as f:
                exec(f.read(), globals())
                return globals().get("COIN_IDS", {})
        except Exception as e:
            print(f"Error loading token mappings: {e}")
            return {}
        
    def get_coin_id(self, symbol: str) -> str:
        """Get CoinGecko ID for a coin symbol"""
        symbol_lower = symbol.lower()
        return self.coin_ids.get(symbol_lower)
        
    def update_coingecko_cache(self):
        """Fetch and cache new data from CoinGecko"""
        current_time = time.time()
        all_data = []
        
        for page in range(1, 10):
            retries = 3
            while retries > 0:
                try:
                    print(f"Fetching CoinGecko data page {page}...")
                    data = self.cg.get_coins_markets(
                        vs_currency="usd",
                        order="market_cap_desc",
                        per_page=250,
                        page=page
                    )
                    all_data.extend(data)
                    time.sleep(1.5)  # Rate limiting
                    break
                except Exception as e:
                    retries -= 1
                    if '429' in str(e):
                        wait_time = 61
                        print(f"Rate limit hit, waiting {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        print(f"Error fetching data: {e}")
                        if retries == 0:
                            raise

        # Add timestamps to data
        for entry in all_data:
            entry['_timestamp'] = current_time

        # Save to cache
        self.cache_dir.mkdir(exist_ok=True)
        with open(self.cache_file, 'w') as f:
            json.dump(all_data, f)

        return all_data
        
    def load_from_cache(self):
        """Load market data from cache, fetching new data if needed"""
        current_time = time.time()
        
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r') as f:
                data = json.load(f)
                if data and '_timestamp' in data[0]:
                    cache_age = current_time - data[0]['_timestamp']
                    if cache_age < self.max_cache_hours * 3600:
                        return data
        
        return self.update_coingecko_cache()
        
    def upload_to_google_sheets(self, df):
        """Upload analysis results to Google Sheets"""
        try:
            # Open the spreadsheet
            doc = self.client.open_by_url(os.getenv("GOOGLE_SHEET_URL"))
            worksheet = doc.get_worksheet(0)
            
            # Get existing data
            existing_data = worksheet.get_all_values()
            
            # Update values in existing data
            df = df.iloc[:-1]  # Remove the last row (usually totals)
            df = df.fillna(0)
            
            for index, row in df.iterrows():
                symbol = row["Pair"]
                matching_row_index = next(
                    (i for i, existing_row in enumerate(existing_data) 
                     if existing_row[0] == symbol), None
                )
                
                if matching_row_index is not None:
                    existing_row = existing_data[matching_row_index]
                    for col_name in df.columns[1:]:
                        if str(row[col_name]) != existing_row[df.columns.get_loc(col_name)]:
                            existing_row[df.columns.get_loc(col_name)] = row[col_name]
                else:
                    new_row = [str(row[col_name]) for col_name in df.columns]
                    existing_data.append(new_row)
            
            # Update the sheet
            worksheet.update("A1", existing_data)
            
            # Update header
            new_header = df.columns.tolist()
            header_update = [new_header]
            worksheet.update(
                'A1:' + chr(64+len(new_header)) + '1', 
                header_update
            )
            
            print("Data updated in Google Sheets.")
            
        except Exception as e:
            logger.error(f"Error uploading to Google Sheets: {e}")
            raise
            
    def format_market_cap(self, cap):
        """Format market cap into human readable string"""
        try:
            cap = float(cap)
        except (ValueError, TypeError):
            return "0"
            
        if cap >= 1e9:
            return f"{cap/1e9:.1f}B"
        elif cap >= 1e6:
            return f"{cap/1e6:.1f}M"
        else:
            return f"{cap:.1f}"

    def get_market_data(self, coin_id):
        """Get market data from CoinGecko"""
        # Current getcap_o.py logic here
        pass 

    def inspect_cache(self, search_token=None):
        """
        Inspect the contents of the CoinGecko cache
        
        Args:
            search_token (str): Optional token symbol to search for
        """
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r') as f:
                data = json.load(f)
                if data and '_timestamp' in data[0]:
                    cache_time = datetime.fromtimestamp(data[0]['_timestamp'])
                    print(f"\nCache last updated: {cache_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"Total coins in cache: {len(data)}")
                    
                    # Create a sorted list of coins with their details
                    coin_list = []
                    for coin in data:
                        coin_list.append({
                            'symbol': coin.get('symbol', '').upper(),
                            'id': coin.get('id', ''),
                            'market_cap': self.format_market_cap(coin.get('market_cap', 0)),
                            'price': coin.get('current_price', 0),
                            'name': coin.get('name', '')
                        })
                    
                    # Filter by search token if provided
                    if search_token:
                        search_term = search_token.upper()
                        coin_list = [
                            coin for coin in coin_list 
                            if search_term in coin['symbol'].upper() 
                            or search_term in coin['id'].upper()
                            or search_term in coin['name'].upper()
                        ]
                        if not coin_list:
                            print(f"\nNo matches found for '{search_token}'")
                            return None
                        print(f"\nFound {len(coin_list)} matches for '{search_token}':")
                    
                    # Sort by symbol
                    coin_list.sort(key=lambda x: x['symbol'])
                    
                    print("\nCached coins:")
                    print("=" * 100)
                    print(f"{'Symbol':<10} {'Name':<20} {'ID':<25} {'Market Cap':<15} {'Price':<10}")
                    print("-" * 100)
                    for coin in coin_list:
                        print(f"{coin['symbol']:<10} {coin['name'][:18]:<20} {coin['id']:<25} {coin['market_cap']:<15} {coin['price']:<10}")
                    print("=" * 100)
                    return data
        print("\nNo cache file found or cache is empty")
        return None 

    def interactive_token_mapping(self, symbol):
        """
        Interactively match token symbols with CoinGecko IDs
        First tries exact symbol match, then falls back to interactive selection
        
        Args:
            symbol (str): Token symbol to search for
        Returns:
            str: Selected coin ID or None if not found
        """
        search_term = symbol.upper()
        exact_matches = []
        
        # Search in cache for exact symbol matches
        cache_data = self.load_from_cache()
        for coin in cache_data:
            if coin.get('symbol', '').upper() == search_term:
                exact_matches.append({
                    'symbol': coin.get('symbol', '').upper(),
                    'name': coin.get('name', ''),
                    'id': coin.get('id', ''),
                    'market_cap': self.format_market_cap(coin.get('market_cap', 0))
                })
        
        # If no exact matches found
        if not exact_matches:
            print(f"\nNo exact matches found for symbol '{symbol}'")
            return None
        
        # If exactly one match found
        if len(exact_matches) == 1:
            print(f"\nFound exact match for {symbol}: {exact_matches[0]['name']} ({exact_matches[0]['id']})")
            return exact_matches[0]['id']
        
        # Multiple exact matches found - ask user to select
        print(f"\nMultiple exact matches found for {symbol}:")
        print("=" * 80)
        print(f"{'#':<3} {'Symbol':<10} {'Name':<30} {'ID':<25} {'Market Cap':<12}")
        print("-" * 80)
        
        for idx, coin in enumerate(exact_matches, 1):
            print(f"{idx:<3} {coin['symbol']:<10} {coin['name'][:28]:<30} {coin['id']:<25} {coin['market_cap']:<12}")
        
        while True:
            try:
                choice = input("\nEnter number of correct token (or 0 to skip): ")
                if not choice.strip():
                    return None
                choice = int(choice)
                if choice == 0:
                    return None
                if 1 <= choice <= len(exact_matches):
                    return exact_matches[choice-1]['id']
                print("Invalid number, please try again")
            except ValueError:
                print("Please enter a valid number")

    def update_token_mappings(self, new_mappings):
        """Update tokens.py with new mappings"""
        try:
            if not os.path.exists("tokens.py"):
                # Create new tokens.py file
                content = "COIN_IDS = {\n"
                for key, value in sorted(new_mappings.items()):
                    content += f'    "{key}": "{value}",\n'
                content += "}\n"
                
                with open("tokens.py", "w") as f:
                    f.write(content)
                print("Created new tokens.py file with mappings")
                return
            
            # Read existing mappings
            with open("tokens.py", "r") as f:
                content = f.read()
            
            # Parse existing COIN_IDS dictionary
            start = content.find("{")
            end = content.rfind("}")
            if start == -1 or end == -1:
                raise ValueError("Could not parse existing COIN_IDS dictionary")
            
            # Create updated dictionary content
            existing_dict = eval(content[start:end+1])
            existing_dict.update(new_mappings)
            
            # Sort dictionary by keys
            sorted_dict = dict(sorted(existing_dict.items()))
            
            # Format the dictionary content
            dict_content = "{\n"
            for key, value in sorted_dict.items():
                dict_content += f'    "{key}": "{value}",\n'
            dict_content += "}\n"
            
            # Write updated content
            new_content = content[:start] + dict_content
            with open("tokens.py", "w") as f:
                f.write(new_content)
            
            print("Token mappings updated successfully")
            
        except Exception as e:
            print(f"Error updating token mappings: {e}") 