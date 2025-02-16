import pandas as pd
from datetime import datetime
import os
from pathlib import Path
import pickle

class Analysis:
    def __init__(self, binance_ops, external_services):
        self.binance = binance_ops
        self.external = external_services
        
    def get_cohort(self, cap):
        """
        Classify market cap into cohorts
        Args:
            cap: Market cap value (can be numeric or string like '1.4M' or '2.5B')
        """
        try:
            # If it's already a number
            if isinstance(cap, (int, float)):
                number = cap / 1e6  # Convert to millions
            else:
                # Parse string format (e.g., "1.4M" or "2.5B")
                parts = cap.split()
                if not parts:
                    return "Unknown"
                
                value = float(parts[0])
                if cap.upper().endswith('B'):
                    value *= 1000  # Convert billions to millions
                elif cap.upper().endswith('M'):
                    value = value  # Already in millions
                else:
                    value /= 1e6  # Convert raw value to millions
                number = value

            # Classify based on millions
            if number < 200:
                return "Tiny, <200m"
            elif 200 <= number < 2000:
                return "Small, 200m-2b"
            elif 2000 <= number < 9000:
                return "Big, 2b-9b"
            else:
                return "Huge, >9b"
        except (ValueError, IndexError, TypeError):
            return "Unknown"

    def calculate_percentages(self, df):
        """Calculate percentage values for USD spent and value"""
        # Get total values from the 'TOTAL' row
        total_spent = df.loc[df['Pair'] == 'TOTAL', 'USD_spent'].values[0]
        df['USD_value'] = df['USD_value'].astype(float)
        total_value = df.loc[df['Pair'] == 'TOTAL', 'USD_value'].values[0]

        # Calculate percentages
        df.loc[df['Pair'] != 'TOTAL', 'USD_spent%'] = (df['USD_spent'] / total_spent * 100).round(1)
        df.loc[df['Pair'] != 'TOTAL', 'USD_value%'] = (df['USD_value'] / total_value * 100).round(1)

        # Format values with percentages
        df['USD_spent'] = df['USD_spent'].astype(str)
        df['USD_value'] = df['USD_value'].astype(str)
        df.loc[df['Pair'] != 'TOTAL', 'USD_spent'] = df['USD_spent'] + " (" + df['USD_spent%'].astype(str) + "%)"
        df.loc[df['Pair'] != 'TOTAL', 'USD_value'] = df['USD_value'] + " (" + df['USD_value%'].astype(str) + "%)"

        return df.drop(columns=["USD_spent%", "USD_value%"])

    def analyze_trades(self):
        """Main analysis function"""
        # Get trade data
        trades_df, total_balance = self.binance.get_trades_analysis_data()
        
        # Get market data
        market_data = self.external.load_from_cache()
        dt_object = datetime.fromtimestamp(market_data[0]['_timestamp'])
        last_cache_update = dt_object.strftime('%m-%d %H:%M')

        # Track unmapped tokens
        unmapped_tokens = set()
        new_mappings = {}

        # Create price and market cap dictionaries
        prices_dict = {coin["id"]: coin["current_price"] for coin in market_data}
        market_caps_dict = {coin["id"]: coin["market_cap"] for coin in market_data}
        fully_diluted_valuation = {coin["id"]: coin["fully_diluted_valuation"] for coin in market_data}

        # Initialize output DataFrame
        columns = [
            "Pair", "#Tr", "USD_spent", "USD_value", "PnL", "pnl%",
            "AvPr", "CrPr", "Pr_diff%", "BuyExtr$", "Expct T",
            "Avlbl T", "USD_sell", f"MC{last_cache_update}", "Cohort"
        ]
        output_df = output_df_sold = pd.DataFrame(columns=columns)

        # Process each trading pair
        grouped = trades_df.groupby("symbol")
        total_mcap = 0

        print("\nProcessing trades and checking token mappings...")
        
        for symbol, group in grouped:
            if symbol in self.binance.pairs_to_skip:
                continue

            coin_symbol = symbol.split('/')[0].lower()
            
            # Check if we need to map this token
            coin_id = self.external.get_coin_id(coin_symbol)
            if not coin_id:
                print(f"\nToken {coin_symbol.upper()} not found in existing mappings")
                coin_id = self.external.interactive_token_mapping(coin_symbol)
                if coin_id:
                    new_mappings[coin_symbol] = coin_id
                else:
                    unmapped_tokens.add(coin_symbol.upper())
                
            # Calculate trade metrics
            num_trades = len(group)
            usd_spent_buy = group[group["side"] == "buy"]["cost"].sum()
            bought_tokens = group[group["side"] == "buy"]["amount"].sum()
            sell_tokens = group[group["side"] == "sell"]["amount"].sum()
            usd_spent_sell = group[group["side"] == "sell"]["cost"].sum()
            
            actual_token_balance = total_balance.get(coin_symbol, 0)
            current_balance = self.binance.get_current_balance(group, actual_token_balance)

            # Get market data
            current_price = prices_dict.get(coin_id, 0)
            raw_mcap = market_caps_dict.get(coin_id, 
                      fully_diluted_valuation.get(coin_id, 0))
            
            # Calculate cohort from raw market cap
            cohort = self.get_cohort(raw_mcap)
            
            # Format market cap for display
            coin_cap = self.external.format_market_cap(raw_mcap)

            total_mcap = float(total_mcap) + float(market_caps_dict.get(coin_id, 0))
            current_usd_value = current_balance * current_price

            # Calculate average price
            if current_balance > 0 and (usd_spent_buy - usd_spent_sell) > 0:
                avpr = usd_spent_buy / bought_tokens
            elif usd_spent_buy > 0:
                avpr = usd_spent_buy / bought_tokens
            else:
                avpr = current_price

            # Calculate price difference and PnL
            pricedf = int(((current_price - avpr) / avpr) * 100)
            if usd_spent_buy == 0:
                usd_spent_buy = current_usd_value + usd_spent_sell
            pricedf_test = (current_usd_value + usd_spent_sell) * 100 / usd_spent_buy - 100

            # Calculate additional purchase recommendation
            adpch = (
                (self.binance.additional_purchase(current_balance, avpr, current_price)
                 * current_price * -1).astype(int)
                if pricedf < 0 else -1
            )

            # Create row data
            new_row_data = {
                "Pair": symbol,
                "#Tr": num_trades,
                "USD_spent": round(usd_spent_buy - usd_spent_sell, 1),
                "USD_value": round(current_usd_value, 1),
                "PnL": round((current_usd_value - usd_spent_buy + usd_spent_sell)),
                "pnl%": f"{round(pricedf_test)}%",
                "AvPr": round(avpr, 3),
                "CrPr": round(current_price, 3),
                "Pr_diff%": f"{round(pricedf)}%",
                "BuyExtr$": adpch,
                "Expct T": round(current_balance, 2),
                "Avlbl T": round(actual_token_balance, 2),
                "USD_sell": round(usd_spent_sell, 0),
                f"MC{last_cache_update}": coin_cap,
                "Cohort": cohort,
            }

            # Add to appropriate DataFrame
            new_row = pd.DataFrame([new_row_data])
            if current_balance > 0:
                if not new_row.isna().all().any():
                    output_df = pd.concat([output_df, new_row], ignore_index=True)
            else:
                if not new_row.isna().all().any():
                    output_df_sold = pd.concat([output_df_sold, new_row], ignore_index=True)

        # Sort and combine results
        output_df = output_df.sort_values("USD_value", ascending=False)
        output_df = pd.concat([output_df, output_df_sold], ignore_index=True)

        # Calculate totals
        total_buy = output_df["USD_spent"].sum()
        total_trades = output_df["#Tr"].sum()
        total_value = output_df["USD_spent"].sum() + output_df["PnL"].sum()
        total_sell = output_df["USD_sell"].sum()
        total_pl = output_df["PnL"].sum()
        total_diff_pnl = total_value * 100 / total_buy - 100 if total_buy != 0 else 0

        # Add totals row
        sums_df = pd.DataFrame([{
            "Pair": "TOTAL",
            "#Tr": total_trades,
            "USD_spent": total_buy.round(1),
            "USD_value": total_value.round(1),
            "PnL": total_pl,
            "pnl%": f"{round(total_diff_pnl, 1)}%",
            "AvPr": "---",
            "CrPr": "---",
            "Pr_diff%": "---",
            "BuyExtr$": "---",
            "Expct T": "---",
            "Avlbl T": "---",
            "USD_sell": total_sell,
            f"MC{last_cache_update}": "---",
            "Cohort": "---",
        }])

        # Combine and calculate percentages
        output_df = pd.concat([sums_df, output_df], ignore_index=True)
        output_df = self.calculate_percentages(output_df)

        # Update token mappings if new ones were found
        if new_mappings:
            print("\nUpdating token mappings with new entries...")
            self.external.update_token_mappings(new_mappings)
        
        # Report unmapped tokens
        if unmapped_tokens:
            print("\nWarning: The following tokens were not found in cache:")
            print(", ".join(sorted(unmapped_tokens)))
            print("Please add them manually to tokens.py if needed")

        return self.save_results(output_df)

    def save_results(self, output_df):
        """Save analysis results and create backup"""
        output_folder = "data"
        filename = "binance_api_analysis.csv"
        output_filename = os.path.join(output_folder, filename)
        backup_folder = "backfiles"

        # Create backup if file exists
        if os.path.exists(output_filename):
            current_datetime = datetime.now().strftime("%Y%m%d_%H%M%S")
            if not os.path.exists(backup_folder):
                os.makedirs(backup_folder)
            backup_filename = os.path.join(backup_folder, f"{current_datetime}_{filename}")
            os.rename(output_filename, backup_filename)
            print(f"Backup created: {backup_filename}")

        # Save new results
        output_df.to_csv(output_filename, index=False)
        
        # Set display options for better output
        pd.set_option('display.max_rows', 1000)
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        pd.set_option('display.float_format', '{:.2f}'.format)
        
        # Print the results
        print("\nAnalysis Results:")
        print("=" * 100)
        print(output_df)
        print("=" * 100)
        
        return output_df 