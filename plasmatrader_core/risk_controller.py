"""
Risk Controller for PlasmaTrader.

Handles risk management, including position sizing and drawdown control,
based on the Kelly Criterion and drawdown protection rules.
"""

import logging
from typing import List, Tuple, Dict
import numpy as np
import pandas as pd

from plasmatrader_core.core_engine import PredictionSignal, Trade, TradingState

# --- Configuration ---
KELLY_HISTORY = 50
MAX_RISK_PER_TRADE = 0.015  # 1.5%
RECOVERY_MODE_RISK = 0.005 # 0.5%
VOLATILITY_PERIODS = 20
VOLATILITY_TARGET = 0.02 # Target 2% daily volatility for scaling

# Drawdown settings
DRAWDOWN_HARD_STOP = 0.08 # 8%
DRAWDOWN_LEVEL_1 = 0.05 # 5%
DRAWDOWN_REDUCTION_STEP = 0.25 # Reduce size by 25% per 1% dd

# Order validation
MIN_ORDER_USD = 10.0
MAX_ORDER_USD = 1000.0

logger = logging.getLogger(__name__)

class RiskManager:
    """
    Encapsulates all risk management logic for the trading bot.
    """

    def _calculate_win_rate_and_odds(self, trades: List[Trade]) -> Tuple[float, float]:
        """
        Calculates win rate (p) and odds (b) from recent trade history.
        Odds (b) is the ratio of average win amount to average loss amount.
        """
        recent_trades = trades[-KELLY_HISTORY:]
        if len(recent_trades) < 20: # Need a minimum number of trades for stats
            return 0.5, 1.0  # Default conservative values

        wins = [t.pnl for t in recent_trades if t.pnl > 0]
        losses = [abs(t.pnl) for t in recent_trades if t.pnl <= 0]

        if not wins or not losses:
            return 0.5, 1.0

        win_rate = len(wins) / len(recent_trades)
        avg_win = sum(wins) / len(wins)
        avg_loss = sum(losses) / len(losses)

        odds = avg_win / avg_loss if avg_loss > 0 else float('inf')
        return win_rate, odds

    def _calculate_realized_volatility(self, historical_data: Dict[str, pd.DataFrame]) -> float:
        """
        Calculates the 20-period realized volatility from the 1h timeframe.
        """
        if '1h' not in historical_data or historical_data['1h'].empty:
            return VOLATILITY_TARGET

        df = historical_data['1h']
        returns = df['close'].pct_change().dropna()
        if len(returns) < VOLATILITY_PERIODS:
            return VOLATILITY_TARGET

        # Using 20-period volatility, not annualized
        vol = returns.rolling(window=VOLATILITY_PERIODS).std().iloc[-1]
        return vol if np.isfinite(vol) and vol > 0 else VOLATILITY_TARGET

    def check_drawdown(self, state: TradingState) -> Tuple[float, bool]:
        """
        Checks the current drawdown and returns a risk adjustment factor.
        Also returns a boolean indicating if a hard stop is triggered.
        """
        drawdown = state.risk_metrics.current_drawdown

        if drawdown >= DRAWDOWN_HARD_STOP:
            logger.warning(f"Drawdown HARD STOP triggered at {drawdown:.2%}.")
            return 0.0, True

        if drawdown >= DRAWDOWN_LEVEL_1:
            dd_steps = int((drawdown - DRAWDOWN_LEVEL_1) / 0.01)
            reduction = (dd_steps + 1) * DRAWDOWN_REDUCTION_STEP
            factor = max(0, 1.0 - reduction)
            logger.info(f"Drawdown of {drawdown:.2%} requires risk reduction. Factor: {factor:.2f}")
            return factor, False

        return 1.0, False

    def calculate_position_size(self, state: TradingState, signal: PredictionSignal, price: float) -> float:
        """
        Calculates the appropriate position size in the base asset (e.g., BTC).
        """
        dd_factor, hard_stop = self.check_drawdown(state)
        if hard_stop:
            return 0.0

        in_recovery_mode = state.wallet_balance < state.risk_metrics.high_water_mark
        max_risk = RECOVERY_MODE_RISK if in_recovery_mode else MAX_RISK_PER_TRADE

        win_rate, odds = self._calculate_win_rate_and_odds(state.trades)
        kelly_fraction = (win_rate * odds - (1 - win_rate)) / odds if odds > 0 else 0.0

        target_risk_pct = max(0, kelly_fraction * 0.5) # 50% Kelly
        final_risk_pct = min(target_risk_pct, max_risk)

        volatility = self._calculate_realized_volatility(state.historical_data)
        vol_adj_factor = min(1.0, VOLATILITY_TARGET / volatility)

        final_risk_pct *= dd_factor * vol_adj_factor

        if final_risk_pct <= 0:
            return 0.0

        position_size_usd = state.wallet_balance * final_risk_pct
        position_size_usd = max(MIN_ORDER_USD, min(position_size_usd, MAX_ORDER_USD))

        if position_size_usd > state.wallet_balance:
            position_size_usd = state.wallet_balance

        if price <= 0: return 0.0
        position_size_asset = position_size_usd / price

        logger.info(
            f"Position Size Calc: Kelly={kelly_fraction:.2f}, Risk%={final_risk_pct:.4f}, "
            f"DD_Factor={dd_factor:.2f}, Vol_Factor={vol_adj_factor:.2f} -> "
            f"SizeUSD={position_size_usd:.2f}, SizeAsset={position_size_asset:.6f}"
        )

        return position_size_asset
