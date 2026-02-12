# Pelosi-Tracker

Automated tracking and trading system that monitors Nancy Pelosi's stock portfolio and executes trades based on her holdings using Alpaca API.

## Overview

This project scrapes Nancy Pelosi's current stock holdings from [PelosiTracker.app](https://pelositracker.app/portfolios/nancy-pelosi) and automatically executes trades to match her portfolio allocation. The system runs daily via GitHub Actions at market open. First of i wanted to use an API but there was none that was good enough and free i wanted to use, so i went with scraping this amazing website(check it out, shout out to these guys. great work!). This project is completely vibe-coded and i will not be liable for any losses or so one, i personally only run it on a paper trading account and i would advise you to do the same. The Project was in the back of my head for a long time i do understand what is going on but AI(in my case Cursor) is just way faster. There will be alot of commits of me fixing AI's mistakes and VERY dumb mistakes, but that alright. Problems like not being able to invest in IBTA.L are fine to me, but if you ant to folow the portfolio too 100%, you must look for another broker and adjust the position manager accordingly.

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

### Order Settings

Configure order behavior via environment variables:

- `DRY_RUN`: Set to `true` to test without executing real trades
- `MIN_ORDER_SIZE`: Minimum order size in dollars (default: 1.0)
- `MAX_ORDER_SIZE`: Maximum order size in dollars (default: 150000.0)

## Workflow Schedule

The GitHub Actions workflow runs:
- **Cron**: `30 14 * * 1-5` (Monday-Friday at 2:30 PM UTC - at market open)
- **Manual**: Can be triggered via GitHub Actions UI

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

**⚠️ Warning**: Always test with paper trading before using real money. Trading involves substantial risk of loss.
