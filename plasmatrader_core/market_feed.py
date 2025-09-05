"""
Market Feed for PlasmaTrader.

Handles connection to Binance WebSocket and market data processing.
"""
import datetime
import json
import logging
import threading
import time
from typing import Callable, Dict, List, Tuple

import pandas as pd
import requests
import websocket

from plasmatrader_core.core_engine import MarketData

# --- Configuration ---
BINANCE_REST_API_URL = "https://api.binance.com/api/v3/klines"
BINANCE_WS_URLS = [
    "wss://stream.binance.com:9443/ws",
    "wss://stream.binance.com:443/ws",
]
SYMBOL = "btcusdt"
CONNECT_TIMEOUT = 10
PING_INTERVAL = 20
PING_TIMEOUT = 10
MAX_RECONNECT_DELAY = 60

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Helper Classes & Functions ---

class MarketMicrostructure:
    """A collection of static methods to calculate market microstructure metrics."""

    @staticmethod
    def calculate_relative_spread(ask: float, bid: float) -> float:
        """Calculates the relative spread in basis points (bps)."""
        if ask <= 0 or bid <= 0:
            return 0.0
        mid_price = (ask + bid) / 2
        if mid_price == 0:
            return 0.0
        return ((ask - bid) / mid_price) * 10000

    @staticmethod
    def calculate_buy_sell_pressure(bids: List[Tuple[float, float]], asks: List[Tuple[float, float]]) -> float:
        """Calculates the bid/ask volume ratio."""
        total_bid_volume = sum(qty for _, qty in bids)
        total_ask_volume = sum(qty for _, qty in asks)
        if total_ask_volume == 0:
            return float('inf') if total_bid_volume > 0 else 1.0
        return total_bid_volume / total_ask_volume

    @staticmethod
    def calculate_instant_liquidity(bids: List[Tuple[float, float]], asks: List[Tuple[float, float]]) -> float:
        """Calculates the total USD value in the top 5 levels of the order book."""
        total_bid_value = sum(price * qty for price, qty in bids)
        total_ask_value = sum(price * qty for price, qty in asks)
        return total_bid_value + total_ask_value

def fetch_historical_klines(symbol: str, interval: str, limit: int = 1000) -> pd.DataFrame:
    """
    Fetches historical k-line (candlestick) data from Binance REST API.
    """
    params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
    try:
        response = requests.get(BINANCE_REST_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        df = pd.DataFrame(data, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])

        # Convert columns to appropriate types
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        for col in ['open', 'high', 'low', 'close', 'volume', 'quote_asset_volume']:
            df[col] = pd.to_numeric(df[col])

        return df[['open_time', 'open', 'high', 'low', 'close', 'volume']]

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching historical data for {symbol}/{interval}: {e}")
        return pd.DataFrame()


class BinanceWebSocketManager:
    """
    Manages the connection to Binance WebSocket streams for real-time market data.
    """

    def __init__(self, symbol: str, callback: Callable[[MarketData], None]):
        self.symbol = symbol.lower()
        self.callback = callback
        self._urls = [f"{url}/{self.symbol}@ticker/{self.symbol}@depth5@100ms/{self.symbol}@trade" for url in BINANCE_WS_URLS]
        self._ws = None
        self._thread = None
        self._stop_event = threading.Event()
        self._data_cache = {} # To aggregate data from different streams

    def start(self):
        """Starts the WebSocket connection in a background thread."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("WebSocket manager already running.")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_websocket, daemon=True)
        self._thread.start()
        logger.info("WebSocket manager started.")

    def stop(self):
        """Stops the WebSocket connection."""
        self._stop_event.set()
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass # Ignore errors on close
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("WebSocket manager stopped.")

    def _run_websocket(self):
        """The main loop for the WebSocket connection thread."""
        reconnect_delay = 1
        url_index = 0
        while not self._stop_event.is_set():
            try:
                url = self._urls[url_index]
                logger.info(f"Connecting to WebSocket: {url}")
                self._ws = websocket.create_connection(
                    url,
                    timeout=CONNECT_TIMEOUT,
                    ping_interval=PING_INTERVAL,
                    ping_timeout=PING_TIMEOUT
                )
                logger.info("WebSocket connection established.")
                reconnect_delay = 1  # Reset delay on successful connection

                while not self._stop_event.is_set():
                    message = self._ws.recv()
                    self._handle_message(message)

            except websocket.WebSocketConnectionClosedException:
                logger.warning("WebSocket connection closed. Reconnecting...")
            except ConnectionError as e:
                logger.error(f"Connection error: {e}. Reconnecting...")
            except TimeoutError as e:
                logger.error(f"Timeout error: {e}. Reconnecting...")
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}. Continuing...")
                continue # Don't reconnect for a bad message
            except KeyError as e:
                logger.error(f"KeyError in message processing: {e}. Using last valid value if possible.")
                continue # Don't reconnect
            except Exception as e:
                logger.critical(f"An unexpected error occurred: {e}. Attempting to reconnect...")

            if self._stop_event.is_set():
                break

            # If an error occurred, wait and try to reconnect
            time.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, MAX_RECONNECT_DELAY)
            url_index = (url_index + 1) % len(self._urls) # Switch to backup URL

    def _handle_message(self, message: str):
        """Parses a message and triggers the callback."""
        try:
            data = json.loads(message)
            stream = data.get('stream')
            payload = data.get('data')

            if not stream or not payload:
                return

            now = datetime.datetime.now(datetime.timezone.utc)

            # Update cache based on stream type
            if '@ticker' in stream:
                self._data_cache['price'] = float(payload['c'])
                self._data_cache['bid'] = float(payload['b'])
                self._data_cache['ask'] = float(payload['a'])
                self._data_cache['timestamp'] = now # Use ticker as heartbeat
            elif '@depth' in stream:
                self._data_cache['top_5_bids'] = [(float(p), float(q)) for p, q in payload['bids']]
                self._data_cache['top_5_asks'] = [(float(p), float(q)) for p, q in payload['asks']]
            elif '@trade' in stream:
                self._data_cache['trade_volume'] = float(payload['q'])

            # If we have the core ticker data, we can form a MarketData object
            if 'price' in self._data_cache and 'timestamp' in self._data_cache:
                # Create a MarketData object, using cached values or defaults
                market_data = MarketData(
                    timestamp=self._data_cache['timestamp'],
                    symbol=self.symbol.upper(),
                    price=self._data_cache['price'],
                    bid=self._data_cache.get('bid', 0.0),
                    ask=self._data_cache.get('ask', 0.0),
                    spread=MarketMicrostructure.calculate_relative_spread(
                        self._data_cache.get('ask', 0.0), self._data_cache.get('bid', 0.0)
                    ),
                    top_5_bids=self._data_cache.get('top_5_bids', []),
                    top_5_asks=self._data_cache.get('top_5_asks', []),
                    trade_volume=self._data_cache.get('trade_volume', 0.0)
                )
                self.callback(market_data)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error(f"Error processing message: {message}. Error: {e}")
