from binance_operations import BinanceOperations
from external_services import ExternalServices
from analysis import Analysis
import os
from pathlib import Path
import argparse
import pandas as pd

def main(skip_fetch=False, show_cache=False, analyze_only=False, search_token=None):
    """
    Run the analysis with various options
    
    Args:
        skip_fetch (bool): If True, skips fetching new data and uses existing CSV files
        show_cache (bool): If True, shows contents of the CoinGecko cache
        analyze_only (bool): If True, runs analysis without uploading to Google Sheets
        search_token (str): Token symbol to search for in cache
    """
    # Initialize components
    binance = BinanceOperations()
    external = ExternalServices()
    analysis = Analysis(binance, external)
    
    # Set pandas display options for better output
    pd.set_option('display.max_rows', 1000)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.float_format', '{:.2f}'.format)
    
    if show_cache:
        external.inspect_cache(search_token)
        return
    
    if not skip_fetch:
        # Update external data
        print("Fetching new data...")
        external.update_coingecko_cache()
        binance.fetch_all_trades()
    else:
        print("Using existing data files...")
    
    # Run analysis
    results = analysis.analyze_trades()
    
    # Handle upload based on mode
    if analyze_only:
        upload = input("\nUpload to Google Sheets? (y/n): ").lower()
        if upload == 'y':
            external.upload_to_google_sheets(results)
    else:
        external.upload_to_google_sheets(results)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Binance Trade Analysis Tool')
    parser.add_argument('--skip-fetch', action='store_true', 
                       help='Skip fetching new data and use existing files')
    parser.add_argument('--show-cache', action='store_true',
                       help='Show contents of the CoinGecko cache')
    parser.add_argument('--analyze-only', action='store_true',
                       help='Run analysis only with optional upload prompt')
    parser.add_argument('search_token', nargs='?', default=None,
                       help='Token symbol to search for in cache (e.g., BTC)')
    args = parser.parse_args()
    
    main(skip_fetch=args.skip_fetch, 
         show_cache=args.show_cache,
         analyze_only=args.analyze_only,
         search_token=args.search_token) 