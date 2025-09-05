"""
CLI Monitor for PlasmaTrader.

This is the main entry point for the application. It starts the trading engine
in a background thread and displays a real-time dashboard of the bot's status
and performance.
"""
import datetime
import logging
import os
import signal
import sys
import threading
import time
from typing import Dict, Any

# Ensure the package is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from plasmatrader_core import core_engine
from plasmatrader_core.paper_trader import PaperTradingEngine

# --- Basic Logging Config ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='plasmatrader.log',
    filemode='w'
)

class MetricsCollector:
    """Calculates and formats metrics for the dashboard."""

    def __init__(self):
        self.paper_trader = PaperTradingEngine()

    def collect(self, cli_state: Dict[str, Any]) -> Dict[str, str]:
        metrics: Dict[str, str] = {}
        state = cli_state.get('state')
        market_data = cli_state.get('market_data')

        status_msg = cli_state.get('status', 'INITIALIZING...')
        if not state or not market_data:
            return {"status": status_msg}

        price = market_data.price
        metrics['price_line'] = f"BTC/USDT: ${price:,.2f}"

        decision = cli_state.get('last_decision', 'ANALYZING')
        confidence = cli_state.get('last_confidence', 0.0)
        metrics['bot_decision'] = f"Bot Decision: {decision} (Confidence: {confidence:.1%})"

        # Placeholders for more detailed signal info
        metrics['chronos_signal'] = "└─ Chronos Signal: (details in log)"
        metrics['entry_logic'] = "└─ Entry Logic: (details in log)"

        position = state.positions.get(core_engine.SYMBOL)
        if position:
            unrealized_pnl = self.paper_trader.calculate_unrealized_pnl(state, market_data)
            pnl_value = unrealized_pnl.get(core_engine.SYMBOL, 0.0)
            entry_value = position.size * position.entry_price
            pnl_pct = (pnl_value / entry_value) * 100 if entry_value > 0 else 0.0

            metrics['active_position'] = f"Active Position: {position.side} {position.size:.5f} BTC @ ${position.entry_price:,.2f}"
            metrics['current_pnl'] = f"Current P&L: ${pnl_value:+.2f} ({pnl_pct:+.3f}%)"
        else:
            metrics['active_position'] = "Active Position: NONE"
            metrics['current_pnl'] = "Current P&L: $0.00"

        total_trades = len(state.trades)
        wins = sum(1 for t in state.trades if t.pnl > 0)
        win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0.0

        metrics['total_trades'] = f"├─ Total Trades: {total_trades}"
        metrics['win_rate'] = f"├─ Win Rate: {win_rate:.1f}%"
        metrics['total_pnl'] = f"├─ Total P&L: ${state.total_pnl:+.2f} ({(state.total_pnl / core_engine.INITIAL_BALANCE) * 100:+.2f}%)"
        metrics['wallet_balance'] = f"└─ Wallet Balance: ${state.wallet_balance:,.2f} USDT"

        risk_pct = state.risk_metrics.current_drawdown * 100
        metrics['system_status'] = f"System: ●{status_msg} │ Feed: ●STABLE │ Risk: {risk_pct:.0f}%"

        return metrics

class DashboardRenderer:
    """Renders the dashboard to the console."""

    def display(self, metrics: Dict[str, str]):
        os.system('cls' if os.name == 'nt' else 'clear')

        print("┌─ PlasmaTrader v3.0 Core ─────────────────────────────┐", flush=True)
        print(f"│ {metrics.get('price_line', ''):<52} │", flush=True)
        print("│                                                      │", flush=True)
        print(f"│ {metrics.get('bot_decision', 'Bot Decision: ...'):<52} │", flush=True)
        print(f"│ {metrics.get('chronos_signal', '└─ Chronos Signal: ...'):<52} │", flush=True)
        print(f"│ {metrics.get('entry_logic', '└─ Entry Logic: ...'):<52} │", flush=True)
        print("│                                                      │", flush=True)
        print(f"│ {metrics.get('active_position', 'Active Position: ...'):<52} │", flush=True)
        print(f"│ {metrics.get('current_pnl', 'Current P&L: ...'):<52} │", flush=True)
        print("│                                                      │", flush=True)
        print("│ Session Stats:                                       │", flush=True)
        print(f"│ {metrics.get('total_trades', '├─ Total Trades: ...'):<52} │", flush=True)
        print(f"│ {metrics.get('win_rate', '├─ Win Rate: ...'):<52} │", flush=True)
        print(f"│ {metrics.get('total_pnl', '├─ Total P&L: ...'):<52} │", flush=True)
        print(f"│ {metrics.get('wallet_balance', '└─ Wallet Balance: ...'):<52} │", flush=True)
        print("│                                                      │", flush=True)
        print(f"│ {metrics.get('system_status', 'System: ●...'):<52} │", flush=True)
        print("└──────────────────────────────────────────────────────┘", flush=True)
        print("Press Ctrl+C to exit. Logs are in plasmatrader.log", flush=True)

def main():
    """Main function to start the application."""
    cli_state: Dict[str, Any] = {'shutdown_requested': False}
    state_lock = threading.Lock()

    def signal_handler(sig, frame):
        print("\nCtrl+C detected. Shutting down gracefully...")
        with state_lock:
            cli_state['shutdown_requested'] = True

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    engine_thread = threading.Thread(
        target=core_engine.main_trading_loop,
        args=(state_lock, cli_state),
        daemon=True
    )
    engine_thread.start()

    collector = MetricsCollector()
    renderer = DashboardRenderer()

    try:
        while engine_thread.is_alive():
            with state_lock:
                current_cli_state = cli_state.copy()

            metrics = collector.collect(current_cli_state)
            renderer.display(metrics)

            if current_cli_state.get('shutdown_requested'):
                break
            time.sleep(1)
    finally:
        print("\nExiting application.")
        engine_thread.join(timeout=10)

if __name__ == "__main__":
    # Add a handler for the root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(logging.FileHandler('plasmatrader.log', 'w'))
    root_logger.setLevel(logging.INFO)

    main()
