#!/usr/bin/env python3
"""
Alpaca Order Manager (copied from RSI Momentum Portfolio)

Reads current_allocation.json and executes orders to match target allocations.
Adapt or extend this script for Pelosi-Tracker as needed.
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Optional
import logging

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
    from alpaca.trading.enums import OrderSide, TimeInForce, OrderStatus
    from alpaca.common.exceptions import APIError
    HAS_ALPACA = True
except ImportError:
    HAS_ALPACA = False
    print("ERROR: alpaca-py not installed. Install with: pip install alpaca-py")
    sys.exit(1)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('order_execution.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Configuration paths
SCRIPT_DIR = Path(__file__).parent
ALLOCATION_FILE = SCRIPT_DIR / "current_allocation.json"

# Default order configuration (can be overridden by environment variables)
DEFAULT_ORDER_CONFIG = {
    'dry_run': False,
    'min_order_size': 10.0,
    'max_order_size': 150000.0,
}

# Crypto ticker mapping: Maps crypto ticker formats to Alpaca trading symbols
# Only needed for crypto assets - regular US stock tickers are used directly
# Format: Maps allocation file ticker -> Alpaca trading symbol
# Example: "BTC-USD" -> "BTC/USD"
CRYPTO_TICKER_MAPPING = {
    "BTC-USD": "BTC/USD",
    "SOL-USD": "SOL/USD",
    # Add other crypto mappings here if needed
}

# Crypto symbols list (both formats: with and without slash)
# Used to identify crypto assets for time_in_force selection
CRYPTO_SYMBOLS = {
    "BTC/USD", "BTCUSD", "BTC-USD",
    "SOL/USD", "SOLUSD", "SOL-USD"
}

# Symbol normalization: maps different formats to a canonical format
# This ensures SOLUSD and SOL/USD are treated as the same asset
SYMBOL_NORMALIZATION = {
    "BTCUSD": "BTC/USD",
    "BTC-USD": "BTC/USD",
    "SOLUSD": "SOL/USD",
    "SOL-USD": "SOL/USD",
}


def normalize_symbol(symbol: str) -> str:
    """Normalize symbol to canonical format (e.g., SOLUSD -> SOL/USD)."""
    return SYMBOL_NORMALIZATION.get(symbol.upper(), symbol)


def load_json_file(filepath: Path) -> dict:
    """Load JSON file with error handling."""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"File not found: {filepath}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {filepath}: {e}")
        raise


def get_alpaca_client() -> TradingClient:
    """Initialize and return Alpaca trading client."""
    api_key = os.getenv('ALPACA_API_KEY')
    secret_key = os.getenv('ALPACA_SECRET_KEY')
    base_url = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
    
    if not api_key or not secret_key:
        raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY must be set as environment variables")
    
    # Determine if paper trading based on base URL
    # Default to paper trading for safety
    is_paper = 'paper-api' in base_url.lower() if base_url else True
    
    logger.info(f"Connecting to Alpaca {'Paper Trading' if is_paper else 'Live Trading'}")
    
    # Create client - paper=True uses paper-api.alpaca.markets automatically
    client = TradingClient(
        api_key=api_key,
        secret_key=secret_key,
        paper=is_paper
    )
    
    return client


def is_market_open(client: TradingClient) -> bool:
    """Check if market is currently open."""
    try:
        clock = client.get_clock()
        return clock.is_open
    except Exception as e:
        logger.warning(f"Could not check market status: {e}")
        return True  # Assume open if check fails


def get_current_positions(client: TradingClient) -> Dict[str, dict]:
    """Get current positions as dict: {symbol: {'value': market_value, 'qty': quantity}}."""
    try:
        positions = client.get_all_positions()
        # Normalize symbols and combine positions with same normalized symbol
        normalized_positions = {}
        for pos in positions:
            normalized_symbol = normalize_symbol(pos.symbol)
            market_value = float(pos.market_value)
            qty = float(pos.qty)
            # If we already have this normalized symbol, add the values and quantities
            if normalized_symbol in normalized_positions:
                normalized_positions[normalized_symbol]['value'] += market_value
                normalized_positions[normalized_symbol]['qty'] += qty
            else:
                normalized_positions[normalized_symbol] = {'value': market_value, 'qty': qty}
        return normalized_positions
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        return {}


def get_account_equity(client: TradingClient) -> float:
    """Get total account equity."""
    try:
        account = client.get_account()
        return float(account.equity)
    except Exception as e:
        logger.error(f"Error getting account info: {e}")
        raise


def calculate_target_positions(allocations: dict, account_equity: float, crypto_mapping: dict = None) -> Dict[str, float]:
    """Calculate target dollar amounts for each position.
    
    Args:
        allocations: Dict with format {ticker: allocation_percentage}
        account_equity: Total account equity in dollars
        crypto_mapping: Optional dict for crypto ticker mappings (e.g., "BTC-USD" -> "BTC/USD")
                       If not provided, tickers are used directly
    
    Returns:
        Dict with format {symbol: target_dollar_value}
    """
    if crypto_mapping is None:
        crypto_mapping = {}
    
    targets = {}
    
    for asset, allocation_pct in allocations.items():
        # Use crypto mapping if available, otherwise use ticker directly
        symbol = crypto_mapping.get(asset, asset)
        target_value = (allocation_pct / 100.0) * account_equity
        targets[symbol] = target_value
    
    return targets


def calculate_orders(current_positions: Dict[str, dict], target_positions: Dict[str, float], 
                    min_order_size: float = 1.0) -> list:
    """Calculate buy/sell orders needed to reach target positions.
    
    Args:
        current_positions: Dict with format {symbol: {'value': market_value, 'qty': quantity}}
        target_positions: Dict with format {symbol: target_market_value}
        min_order_size: Minimum order size in dollars
    
    Returns:
        List of order dicts.
        - Sell orders use 'qty' (shares), rounded to 3 decimal places.
        - Buy orders prefer 'qty' (shares, rounded to 3 decimal places) when an approximate
          price can be inferred from an existing position; otherwise they fall back to
          'notional' (dollars).
    """
    orders = []
    
    # Get all unique symbols
    all_symbols = set(current_positions.keys()) | set(target_positions.keys())
    
    for symbol in all_symbols:
        position_data = current_positions.get(symbol, {'value': 0.0, 'qty': 0.0})
        current_value = position_data.get('value', 0.0)
        current_qty = position_data.get('qty', 0.0)
        
        # Check if symbol is in target_positions (i.e., in the JSON file)
        # If not in target_positions, it was removed from allocation - close completely
        symbol_in_target = symbol in target_positions
        target_value = target_positions.get(symbol, 0.0)
        difference = target_value - current_value
        
        # Always close positions that should be zero:
        # 1. Symbol not in JSON anymore (removed from allocation)
        # 2. Symbol in JSON but target is 0.0
        # This prevents accumulation of residual positions
        should_close_position = (not symbol_in_target or target_value == 0.0) and current_value > 0.0
        
        # Skip if difference is too small, UNLESS we're closing a position
        if not should_close_position and abs(difference) < min_order_size:
            continue
        
        if difference > 0:
            # Need to buy - prefer share quantities when we can infer a price from an existing position
            buy_order = {
                'symbol': symbol,
                'side': 'buy',
            }

            # If we already have a position, infer an approximate price from it
            if current_qty > 0 and current_value > 0:
                approx_price = current_value / current_qty
                # Protect against division edge cases
                if approx_price > 0:
                    buy_qty = difference / approx_price
                    buy_qty = round(buy_qty, 3)  # Match sell rounding: 3 decimal places
                    if buy_qty > 0:
                        buy_order['qty'] = buy_qty
                        orders.append(buy_order)
                        continue
            
            # Fallback: if we cannot infer a price (e.g., new position), use notional dollars
            buy_order['notional'] = round(difference, 2)  # 2 decimal places for Alpaca API
            orders.append(buy_order)
        else:
            # Need to sell - use share quantities
            if not symbol_in_target:
                # Asset removed from JSON - close entire position
                # Sell 100% of current shares, rounded to 3 decimal places
                sell_qty = round(current_qty, 3)
                logger.info(f"Asset {symbol} removed from allocation - closing full position: {current_qty:.3f} shares (${current_value:.2f})")
            elif target_value == 0.0:
                # Target is 0.0 - close entire position
                # Sell 100% of current shares, rounded to 3 decimal places
                sell_qty = round(current_qty, 3)
                logger.info(f"Full position close for {symbol}: {current_qty:.3f} shares (${current_value:.2f})")
            else:
                # Partial sell: calculate shares to sell based on dollar difference
                # Formula: shares_to_sell = current_qty * (current_value - target_value) / current_value
                if current_value > 0:
                    sell_qty = current_qty * (current_value - target_value) / current_value
                    sell_qty = round(sell_qty, 3)  # Round to 3 decimal places
                    # Ensure we don't sell more than we have
                    sell_qty = min(sell_qty, current_qty)
                else:
                    sell_qty = 0.0
                logger.debug(f"Partial sell for {symbol}: current={current_qty:.3f} shares (${current_value:.2f}), target=${target_value:.2f}, selling={sell_qty:.3f} shares")
            
            # Only add order if we have shares to sell
            if sell_qty > 0:
                orders.append({
                    'symbol': symbol,
                    'side': 'sell',
                    'qty': sell_qty,  # Share quantity rounded to 3 decimal places
                    'current_position_value': current_value  # Store for logging
                })
    
    return orders


def execute_order(client: TradingClient, order_data: dict, config: dict) -> bool:
    """Execute a single order.
    
    - Sell orders use qty (shares).
    - Buy orders prefer qty (shares) when provided; if qty is not present, they fall back
      to notional (dollars).
    """
    symbol = order_data['symbol']
    side = order_data['side']
    
    # Determine time_in_force based on asset type and order size
    # Crypto orders must use GTC (DAY not supported for crypto)
    # Fractional stock orders (small amounts) must use DAY
    # Regular stock orders can use DAY
    # Check if symbol is crypto (both formats: "SOL/USD" and "SOLUSD")
    is_crypto = '/' in symbol or symbol.upper() in CRYPTO_SYMBOLS
    
    try:
        if side == 'sell':
            # Sell orders use qty (share quantity)
            qty = order_data.get('qty', 0.0)
            if qty <= 0:
                logger.error(f"Invalid sell quantity for {symbol}: {qty}")
                return False
            
            # Determine time_in_force
            if is_crypto:
                time_in_force = TimeInForce.GTC
            else:
                # For stock sell orders, use DAY
                time_in_force = TimeInForce.DAY
            
            order_request = MarketOrderRequest(
                symbol=symbol,
                side=OrderSide.SELL,
                qty=qty,
                time_in_force=time_in_force
            )
            
            order = client.submit_order(order_data=order_request)
            current_value = order_data.get('current_position_value', 0.0)
            logger.info(f"Order submitted: SELL {qty:.3f} shares of {symbol} (${current_value:.2f}) (Order ID: {order.id})")
            return True
            
        else:
            # Buy orders prefer qty (share quantity) when available
            qty = float(order_data.get('qty', 0.0))
            notional = float(order_data.get('notional', 0.0))

            if qty > 0:
                qty = round(qty, 3)  # Match sell rounding: 3 decimal places
                
                if is_crypto:
                    # Crypto orders (fractional or not) MUST use GTC - DAY is not supported for crypto
                    time_in_force = TimeInForce.GTC
                else:
                    # Stock buy orders use DAY
                    time_in_force = TimeInForce.DAY
                
                order_request = MarketOrderRequest(
                    symbol=symbol,
                    side=OrderSide.BUY,
                    qty=qty,
                    time_in_force=time_in_force
                )
                
                order = client.submit_order(order_data=order_request)
                logger.info(f"Order submitted: BUY {qty:.3f} shares of {symbol} (Order ID: {order.id})")
                return True

            # Fallback: support legacy notional-based buy orders if qty is not provided
            notional = round(notional, 2)
            if notional <= 0:
                logger.error(f"Invalid buy parameters for {symbol}: qty={qty}, notional={notional}")
                return False
            
            if is_crypto:
                # Crypto orders (fractional or not) MUST use GTC - DAY is not supported for crypto
                time_in_force = TimeInForce.GTC
            else:
                # Stock buy orders use DAY
                time_in_force = TimeInForce.DAY
            
            order_request = MarketOrderRequest(
                symbol=symbol,
                side=OrderSide.BUY,
                notional=notional,
                time_in_force=time_in_force
            )
            
            order = client.submit_order(order_data=order_request)
            logger.info(f"Order submitted (fallback notional): BUY ${notional:.2f} of {symbol} (Order ID: {order.id})")
            return True
            
    except APIError as e:
        logger.error(f"API error executing order for {symbol}: {e}")
        return False
    except Exception as e:
        logger.error(f"Error executing order for {symbol}: {e}")
        return False


def main():
    """Main execution function."""
    logger.info("=" * 80)
    logger.info("Order Execution")
    logger.info("=" * 80)
    
    # Load configuration files
    try:
        allocation_data = load_json_file(ALLOCATION_FILE)
    except Exception as e:
        logger.error(f"Failed to load allocation file: {e}")
        sys.exit(1)
    
    # Load order config from environment variables or use defaults
    order_config = DEFAULT_ORDER_CONFIG.copy()
    
    # Override with environment variables if set
    if os.getenv('DRY_RUN'):
        order_config['dry_run'] = os.getenv('DRY_RUN').lower() in ('true', '1', 'yes')
    if os.getenv('MIN_ORDER_SIZE'):
        order_config['min_order_size'] = float(os.getenv('MIN_ORDER_SIZE'))
    if os.getenv('MAX_ORDER_SIZE'):
        order_config['max_order_size'] = float(os.getenv('MAX_ORDER_SIZE'))
    
    logger.info(f"Order config: dry_run={order_config['dry_run']}, min_order_size=${order_config['min_order_size']}")
    
    # Validate allocation file
    if 'allocations' not in allocation_data:
        logger.error("Invalid allocation file: missing 'allocations' key")
        sys.exit(1)
    
    allocations = allocation_data['allocations']
    data_date = allocation_data.get('data_as_of_date', 'unknown')
    logger.info(f"Allocation date: {data_date}")
    logger.info(f"Allocations: {allocations}")
    
    # Initialize Alpaca client
    try:
        client = get_alpaca_client()
        logger.info("Connected to Alpaca API")
    except Exception as e:
        logger.error(f"Failed to connect to Alpaca: {e}")
        sys.exit(1)
    
    # Check if market is open
    if not is_market_open(client):
        logger.warning("Market is closed. Orders will be queued for next market open.")
    
    # Cancel all pending orders to avoid wash trades and conflicting orders
    try:
        pending_orders = client.get_orders(filter=GetOrdersRequest(status='open'))
        
        if pending_orders:
            logger.info(f"Canceling {len(pending_orders)} pending order(s)...")
            for order in pending_orders:
                try:
                    client.cancel_order_by_id(order.id)
                    logger.info(f"  Canceled order {order.id} for {order.symbol}")
                except Exception as cancel_error:
                    logger.warning(f"  Could not cancel order {order.id}: {cancel_error}")
            logger.info("All pending orders processed")
        else:
            logger.info("No pending orders to cancel")
    except Exception as e:
        logger.warning(f"Could not check/cancel pending orders: {e}")
    
    # Get account information
    try:
        account_equity = get_account_equity(client)
        logger.info(f"Account equity: ${account_equity:,.2f}")
    except Exception as e:
        logger.error(f"Failed to get account info: {e}")
        sys.exit(1)
    
    # Get current positions
    current_positions = get_current_positions(client)
    # Log positions in a readable format
    positions_str = {}
    for symbol, pos_data in current_positions.items():
        positions_str[symbol] = f"{pos_data['qty']:.3f} shares (${pos_data['value']:.2f})"
    logger.info(f"Current positions: {positions_str}")
    
    # Calculate target positions - tickers are used directly, crypto mapping only for crypto assets
    target_positions = calculate_target_positions(allocations, account_equity, CRYPTO_TICKER_MAPPING)
    logger.info(f"Target positions: {target_positions}")
    
    # Calculate orders needed
    min_order_size = order_config.get('min_order_size', 1.0)
    orders = calculate_orders(current_positions, target_positions, min_order_size)
    
    if not orders:
        logger.info("No orders needed - portfolio is already at target allocation")
        return
    
    logger.info(f"Calculated {len(orders)} orders to execute")
    for order in orders:
        if order['side'] == 'sell':
            qty = order.get('qty', 0.0)
            current_value = order.get('current_position_value', 0.0)
            logger.info(f"  {order['side'].upper()}: {qty:.3f} shares of {order['symbol']} (${current_value:.2f})")
        else:
            qty = order.get('qty')
            notional = order.get('notional')
            if qty is not None and qty > 0:
                logger.info(f"  {order['side'].upper()}: {qty:.3f} shares of {order['symbol']}")
            else:
                notional = notional or 0.0
                logger.info(f"  {order['side'].upper()}: ${notional:.2f} of {order['symbol']}")
    
    # Sort orders: SELL orders first, then BUY orders
    # This ensures we have cash/assets available before buying
    sell_orders = [o for o in orders if o['side'] == 'sell']
    buy_orders = [o for o in orders if o['side'] == 'buy']
    sorted_orders = sell_orders + buy_orders
    
    if sell_orders:
        logger.info(f"Executing {len(sell_orders)} SELL order(s) first...")
    if buy_orders:
        logger.info(f"Then executing {len(buy_orders)} BUY order(s)...")
    
    # Execute orders
    if order_config.get('dry_run', False):
        logger.info("DRY RUN MODE - No orders will be executed")
        return
    
    logger.info("Executing orders...")
    success_count = 0
    for order in sorted_orders:
        if execute_order(client, order, order_config):
            success_count += 1
    
    logger.info(f"Order execution complete: {success_count}/{len(orders)} orders submitted successfully")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()

