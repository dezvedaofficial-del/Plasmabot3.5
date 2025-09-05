"""
Paper Trader for PlasmaTrader.

Handles simulated trade execution with realistic market conditions, including
slippage, commissions, and latency.
"""
import copy
import datetime
import logging
import random
import time
from dataclasses import dataclass
from typing import Dict

from plasmatrader_core.core_engine import MarketData, Position, Trade, TradingState

# --- Configuration ---
TAKER_FEE = 0.0004
LATENCY_MIN_S = 0.050
LATENCY_MAX_S = 0.200
SLIPPAGE_FACTOR = 0.1

logger = logging.getLogger(__name__)

@dataclass
class Order:
    """Represents a request to execute a trade."""
    timestamp: datetime.datetime
    symbol: str
    side: str  # 'BUY' or 'SELL'
    size: float  # in base asset, e.g., BTC
    type: str = 'MARKET'


class PaperTradingEngine:
    """
    Simulates the execution of trades and updates the trading state.
    """

    def _calculate_slippage(self, order_size: float, market_data: MarketData) -> float:
        """Calculates slippage in price units."""
        if market_data.spread <= 0 or not market_data.top_5_asks:
            return 0.0

        top_level_qty = market_data.top_5_asks[0][1] if market_data.top_5_asks else 1.0
        if top_level_qty == 0: return market_data.spread * SLIPPAGE_FACTOR

        size_ratio = min(order_size / top_level_qty, 1.0)
        spread_price = market_data.ask - market_data.bid
        return spread_price * SLIPPAGE_FACTOR * size_ratio

    def _update_risk_metrics(self, state: TradingState) -> TradingState:
        """Updates HWM and drawdown based on current wallet balance."""
        new_hwm = max(state.risk_metrics.high_water_mark, state.wallet_balance)
        drawdown = (new_hwm - state.wallet_balance) / new_hwm if new_hwm > 0 else 0.0

        state.risk_metrics.high_water_mark = new_hwm
        state.risk_metrics.current_drawdown = drawdown
        return state

    def execute_order(self, order: Order, state: TradingState, market_data: MarketData) -> TradingState:
        """Executes an order, returning a new TradingState object."""
        new_state = copy.deepcopy(state)
        time.sleep(random.uniform(LATENCY_MIN_S, LATENCY_MAX_S))

        slippage = self._calculate_slippage(order.size, market_data)
        exec_price = (market_data.ask + slippage) if order.side == 'BUY' else (market_data.bid - slippage)

        order_cost = order.size * exec_price
        commission = order_cost * TAKER_FEE
        pnl = 0.0

        existing_pos = new_state.positions.get(order.symbol)

        if not existing_pos:
            new_pos = Position(order.symbol, 'LONG' if order.side == 'BUY' else 'SHORT', order.size, exec_price)
            new_state.positions[order.symbol] = new_pos
            new_state.wallet_balance -= (order_cost + commission)
        else:
            is_same_side = (existing_pos.side == 'LONG' and order.side == 'BUY') or \
                           (existing_pos.side == 'SHORT' and order.side == 'SELL')
            if is_same_side:
                new_total_size = existing_pos.size + order.size
                new_entry_price = ((existing_pos.entry_price * existing_pos.size) + (exec_price * order.size)) / new_total_size
                existing_pos.size, existing_pos.entry_price = new_total_size, new_entry_price
                new_state.wallet_balance -= (order_cost + commission)
            else:
                if order.size >= existing_pos.size:
                    closed_size = existing_pos.size
                    entry_cost = closed_size * existing_pos.entry_price
                    exit_cost = closed_size * exec_price
                    pnl = (exit_cost - entry_cost) if existing_pos.side == 'LONG' else (entry_cost - exit_cost)

                    new_state.wallet_balance += pnl - commission
                    new_state.total_pnl += pnl
                    del new_state.positions[order.symbol]

                    if order.size > closed_size:
                        rem_order = Order(order.timestamp, order.symbol, order.side, order.size - closed_size)
                        return self.execute_order(rem_order, new_state, market_data)
                else:
                    reduced_size = order.size
                    entry_cost = reduced_size * existing_pos.entry_price
                    exit_cost = reduced_size * exec_price
                    pnl = (exit_cost - entry_cost) if existing_pos.side == 'LONG' else (entry_cost - exit_cost)

                    existing_pos.size -= reduced_size
                    new_state.wallet_balance += pnl - commission
                    new_state.total_pnl += pnl

        trade = Trade(datetime.datetime.now(datetime.timezone.utc), order.symbol, order.side, exec_price, order.size, pnl, commission)
        new_state.trades.append(trade)
        new_state.timestamp = datetime.datetime.now(datetime.timezone.utc)
        final_state = self._update_risk_metrics(new_state)

        logger.info(f"Executed: {order.side} {order.size:.6f} {order.symbol} @ {exec_price:.2f}. PnL: {pnl:.2f}, Comm: {commission:.2f}, Bal: {final_state.wallet_balance:.2f}")
        return final_state

    def calculate_unrealized_pnl(self, state: TradingState, market_data: MarketData) -> Dict[str, float]:
        """Calculates the mark-to-market P&L for all open positions."""
        pnl = {}
        for symbol, position in state.positions.items():
            entry_cost = position.size * position.entry_price
            current_value = position.size * market_data.price
            pnl[symbol] = (current_value - entry_cost) if position.side == 'LONG' else (entry_cost - current_value)
        return pnl
