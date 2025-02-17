# Binance Portfolio Analyzer

Version: 0.1.0 (Released: 2024-02-25)

## Description
A comprehensive tool for analyzing Binance trading portfolio, providing detailed insights into trading performance, market caps, and portfolio distribution across different market cap cohorts.

## Features
- Automated trade data fetching from Binance
- Real-time market data integration via CoinGecko
- Market cap cohort analysis (Tiny, Small, Big, Huge)
- Intelligent token mapping system
- Google Sheets integration for result sharing
- Smart caching system for API rate limit management
- Interactive token mapping for new assets
- Detailed performance metrics including:
  - PnL calculations
  - Price differences
  - Average prices
  - Current market values
  - Trading volume analysis

## Requirements
- Python 3.8+
- Binance API credentials
- Google Sheets API credentials
- CoinGecko API access

## Installation
1. Clone the repository
2. Install required packages:
   pip install ccxt pandas python-dotenv pycoingecko gspread oauth2client
3. Set up environment variables in .env:
   BINANCE_API_KEY=your_api_key
   BINANCE_SECRET_KEY=your_secret_key
   GOOGLE_SHEET_URL=your_google_sheet_url

## Usage
The tool can be run in several modes:

1. Full analysis with data update:
   python main.py

2. Analysis using existing data:
   python main.py --skip-fetch

3. Analysis only (with optional upload):
   python main.py --analyze-only

4. Check cache contents:
   python main.py --show-cache

5. Search for specific token in cache:
   python main.py --show-cache btc

## Output
- Detailed CSV report with trading metrics
- Google Sheets integration for easy sharing
- Console output with key statistics
- Automatic backup of previous results

## Market Cap Cohorts
- Tiny: < 200M
- Small: 200M - 2B
- Big: 2B - 9B
- Huge: > 9B

## Project Structure
binance-analyzer/
├── main.py              # Main entry point
├── analysis.py          # Analysis logic
├── binance_operations.py # Binance API interactions
├── external_services.py  # External services (CoinGecko, Google)
├── tokens.py            # Token mapping configurations
├── Cache/               # Cache storage
│   ├── coingecko_cache.json
│   └── pair_skip.json
├── Data/                # Data storage
│   └── all_trades.csv
├── backfiles/           # Backup storage
└── old_code/           # Legacy code archive

## Changelog
### 0.1.0 (2024-02-25)
- Initial release
- Implemented core analysis functionality
- Added interactive token mapping
- Integrated CoinGecko market data
- Added cohort analysis
- Implemented Google Sheets integration
- Added command-line interface
- Implemented caching system

## Future Plans
- Enhanced error handling
- Additional performance metrics
- Historical trend analysis
- Custom cohort definitions
- Export to additional formats
- Trading strategy insights

## Contributing
Feel free to submit issues and enhancement requests.

## License
MIT License

## Acknowledgments
- CCXT library for Binance integration
- CoinGecko for market data
- Google Sheets API for data sharing
