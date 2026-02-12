# Pelosi-Tracker

Automated tracking and trading system that monitors Nancy Pelosi's stock portfolio and executes trades based on her holdings using Alpaca API.

## Overview

This project scrapes Nancy Pelosi's current stock holdings from [PelosiTracker.app](https://pelositracker.app/portfolios/nancy-pelosi) and automatically executes trades to match her portfolio allocation. The system runs daily via GitHub Actions at market open.

## Features

- 🔍 **Automated Scraping**: Fetches Nancy Pelosi's current holdings from PelosiTracker.app
- 📊 **Portfolio Tracking**: Monitors ticker symbols, weights, and prices
- 🤖 **Automated Trading**: Executes buy/sell orders via Alpaca API to match target allocations
- ⏰ **Scheduled Execution**: Runs daily via GitHub Actions workflow
- 🛡️ **Error Handling**: Retry logic and error handling for network requests
- 📝 **Logging**: Comprehensive logging for order execution and errors

## Project Structure

```
Pelosi-Tracker/
├── Pelosi-Tracker.ipynb          # Jupyter notebook for scraping Pelosi holdings and generating allocation
├── execute_orders.py               # Alpaca order execution script
├── requirements.txt               # Python dependencies
├── .github/
│   └── workflows/
│       └── daily-allocation.yml   # GitHub Actions workflow
├── current_allocation.json        # Generated allocation file (used by execute_orders.py)
└── README.md
```

## Prerequisites

- Python 3.12+
- Alpaca account (paper or live trading)
- GitHub account (for automated workflows)

## Setup

### 1. Clone the Repository

```bash
git clone git@github.com:nico-108/Pelosi-Tracker.git
cd Pelosi-Tracker
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Alpaca API Keys

#### For Local Development

Set environment variables:

```bash
export ALPACA_API_KEY="your_api_key"
export ALPACA_SECRET_KEY="your_secret_key"
export ALPACA_BASE_URL="https://paper-api.alpaca.markets"  # or https://api.alpaca.markets for live
export DRY_RUN="true"  # Set to "false" for real trades
```

#### For GitHub Actions

1. Go to your repository: `https://github.com/nico-108/Pelosi-Tracker`
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Add the following secrets:
   - `ALPACA_API_KEY`: Your Alpaca API key
   - `ALPACA_SECRET_KEY`: Your Alpaca secret key
   - `ALPACA_BASE_URL`: `https://paper-api.alpaca.markets` (paper) or `https://api.alpaca.markets` (live)
   - `DRY_RUN`: `true` (recommended for testing) or `false`
   - `MIN_ORDER_SIZE`: `1.0` (optional, minimum order size in dollars)

## Usage

### Manual Execution

#### 1. Scrape Pelosi Holdings and Generate Allocation

Run the Jupyter notebook to fetch current holdings and generate the allocation file:

```bash
jupyter notebook Pelosi-Tracker.ipynb
```

Or execute via command line:

```bash
jupyter nbconvert --to notebook --execute Pelosi-Tracker.ipynb
```

This will:
- Scrape Nancy Pelosi's current holdings from PelosiTracker.app
- Generate `current_allocation.json` with the following format:

```json
{
  "data_as_of_date": "2026-02-12",
  "allocations": {
    "NVDA": 19.0,
    "GOOGL": 16.0,
    "AVGO": 16.0,
    "VST": 9.0,
    "PANW": 7.0,
    "TEM": 7.0,
    "AMZN": 6.0,
    "CRWD": 5.0,
    "TSLA": 4.0,
    "MSFT": 3.0,
    "AAPL": 3.0
  }
}
```

#### 2. Execute Orders

Run the order execution script:

```bash
python execute_orders.py
```

The script will:
- Load `current_allocation.json`
- Calculate target positions based on account equity
- Compare with current positions
- Execute buy/sell orders to match target allocation
- Log all actions to `order_execution.log`

### Automated Execution (GitHub Actions)

The workflow runs automatically:
- **Schedule**: Daily at 2:30 PM UTC (at market open) on weekdays
- **Manual Trigger**: Available via GitHub Actions UI

The workflow:
1. Executes `Pelosi-Tracker.ipynb` which scrapes holdings and generates `current_allocation.json`
2. Runs `execute_orders.py` to execute trades based on the allocation
3. Commits and pushes the updated `current_allocation.json` file

## Configuration

### Ticker Mapping

Edit `execute_orders.py` to customize ticker mappings in the `TICKER_MAPPING` dictionary:

```python
TICKER_MAPPING = {
    "NVDA": "NVDA",
    "GOOGL": "GOOGL",
    "AAPL": "AAPL",
    # Add your mappings here
}
```

### Order Settings

Configure order behavior via environment variables:

- `DRY_RUN`: Set to `true` to test without executing real trades
- `MIN_ORDER_SIZE`: Minimum order size in dollars (default: 1.0)
- `MAX_ORDER_SIZE`: Maximum order size in dollars (default: 150000.0)

## Workflow Schedule

The GitHub Actions workflow runs:
- **Cron**: `30 14 * * 1-5` (Monday-Friday at 2:30 PM UTC - at market open)
- **Manual**: Can be triggered via GitHub Actions UI

To modify the schedule, edit `.github/workflows/daily-allocation.yml`.

## Logging

- **Order Execution**: Logged to `order_execution.log`
- **Scraping Errors**: Logged to `scraping_error.log`
- **GitHub Actions**: View logs in the Actions tab

## Safety Features

- ✅ **Dry Run Mode**: Test without real trades
- ✅ **Paper Trading**: Default uses Alpaca paper trading API
- ✅ **Error Handling**: Comprehensive retry logic and error handling
- ✅ **Order Validation**: Minimum/maximum order size limits
- ✅ **Position Closing**: Automatically closes positions removed from allocation

## Important Notes

⚠️ **Disclaimer**: This project is for educational purposes only. Trading involves risk. Always test with paper trading first.

- The system scrapes publicly available data from PelosiTracker.app
- All trades are executed through Alpaca API
- Default configuration uses **paper trading** for safety
- Set `DRY_RUN=true` when testing
- Monitor logs and positions regularly

## Troubleshooting

### Common Issues

**"Could not find holdings table"**
- The website structure may have changed
- Check `scraping_error.log` for details
- Verify PelosiTracker.app is accessible

**"ALPACA_API_KEY not set"**
- Ensure environment variables are configured
- For GitHub Actions, verify secrets are set correctly

**"Market is closed"**
- Orders will be queued for next market open
- Check market hours before executing

**"No orders needed"**
- Portfolio already matches target allocation
- This is normal if positions are up to date

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly with `DRY_RUN=true`
5. Submit a pull request

## License

This project is provided as-is for educational purposes.

## Resources

- [PelosiTracker.app](https://pelositracker.app/portfolios/nancy-pelosi)
- [Alpaca API Documentation](https://alpaca.markets/docs/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)

## Author

[nico-108](https://github.com/nico-108)

[readme written by ai, when questions appear please contact me](https://github.com/nico-108)
---

**⚠️ Warning**: Always test with paper trading and dry run mode before using real money. Trading involves substantial risk of loss.
