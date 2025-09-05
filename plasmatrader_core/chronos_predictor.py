"""
Chronos-Bolt Predictor for PlasmaTrader.

Handles the forecasting using the Chronos-Bolt model, incorporating advanced
optimizations and signal processing as per the system specification.
"""
import concurrent.futures
import gc
import logging
import datetime
import threading
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import torch
from transformers import ChronosConfig, ChronosForCausalLM, ChronosPipeline

from plasmatrader_core.core_engine import PredictionSignal, TradingState

# --- Configuration ---
# The prompt specified 'amazon/chronos-bolt-medium'. Based on public information,
# the 24M parameter model is named 'amazon/chronos-t5-medium'. Using this name
# to ensure the code can fetch the model.
MODEL_NAME = "amazon/chronos-t5-medium"

TIME_FRAMES = ["1m", "3m", "5m", "15m", "30m", "1h"]
TIME_FRAME_WEIGHTS = {
    "1m": 0.1, "3m": 0.15, "5m": 0.2, "15m": 0.25, "30m": 0.15, "1h": 0.15
}
HISTORICAL_WINDOW = 200
PREDICTION_LENGTHS = [1, 3, 5, 10, 15]
VOLATILITY_WINDOW = 20
CONFIDENCE_THRESHOLD = 0.7
TEMPORAL_DECAY_FACTOR = 0.95
MAX_WORKERS = 2

# --- Logging ---
logger = logging.getLogger(__name__)

class ChronosPredictor:
    """
    A singleton class to manage the Chronos model and perform predictions.
    The model is loaded once and quantized for CPU optimization.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ChronosPredictor, cls).__new__(cls)
                    cls._instance._initialize_model()
        return cls._instance

    def _initialize_model(self):
        """Loads and quantizes the Chronos model."""
        try:
            logger.info(f"Initializing Chronos model: {MODEL_NAME}")

            config = ChronosConfig.from_pretrained(MODEL_NAME)
            model = ChronosForCausalLM.from_pretrained(MODEL_NAME, config=config)

            logger.info("Applying int8 dynamic quantization to the model...")
            self.model = torch.quantization.quantize_dynamic(
                model, {torch.nn.Linear}, dtype=torch.qint8
            )

            self.pipeline = ChronosPipeline.from_model(
                self.model,
                task="causal-lm"
            )
            logger.info("Chronos model initialized successfully.")

        except Exception as e:
            logger.critical(f"Failed to initialize Chronos model: {e}", exc_info=True)
            self.pipeline = None

    def predict(self, context: torch.Tensor, prediction_length: int) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generates forecasts for a given context.
        Returns median forecast and confidence interval width.
        """
        if self.pipeline is None:
            raise RuntimeError("Chronos model is not available.")

        forecasts = self.pipeline(
            context,
            prediction_length=prediction_length,
            num_samples=20,
            temperature=1.0,
            top_k=50,
            top_p=1.0,
        )

        # Forecasts is a list of numpy arrays. We passed one context, so we get a list with one element.
        forecast = forecasts[0]
        median = np.median(forecast, axis=0)
        q10 = np.quantile(forecast, 0.1, axis=0)
        q90 = np.quantile(forecast, 0.9, axis=0)

        return median, (q90 - q10)

def _predict_single_timeframe(
    timeframe: str,
    price_series: pd.Series,
    predictor: ChronosPredictor
) -> Tuple[str, float, float]:
    """
    Performs prediction for a single timeframe and returns weighted result.
    """
    try:
        if len(price_series) < HISTORICAL_WINDOW:
            return timeframe, 0.0, 0.0

        context_series = price_series.iloc[-HISTORICAL_WINDOW:]
        context_tensor = torch.tensor(context_series.values, dtype=torch.float32)

        returns = context_series.pct_change().dropna()
        volatility = returns.rolling(window=VOLATILITY_WINDOW).std().iloc[-1]
        if not np.isfinite(volatility): volatility = 0.0

        forecast_median, forecast_ci = predictor.predict(context_tensor, max(PREDICTION_LENGTHS))

        weights = np.array([TEMPORAL_DECAY_FACTOR**i for i in range(len(PREDICTION_LENGTHS))])
        selected_forecasts = forecast_median[[p-1 for p in PREDICTION_LENGTHS]]

        last_price = context_series.iloc[-1]
        if last_price == 0: return timeframe, 0.0, 0.0

        pred_price = np.average(selected_forecasts, weights=weights)
        pred_change_pct = (pred_price - last_price) / last_price

        ci_width = np.mean(forecast_ci[[p-1 for p in PREDICTION_LENGTHS]])
        confidence = 1.0 - (ci_width / last_price)
        confidence = max(0.0, min(1.0, confidence))

        vol_adj_factor = 1.0 - min(volatility * 5, 0.5)
        adj_confidence = confidence * vol_adj_factor

        return timeframe, pred_change_pct, adj_confidence

    except Exception as e:
        logger.error(f"Error in single timeframe prediction for {timeframe}: {e}", exc_info=True)
        return timeframe, 0.0, 0.0

def predict_multi_timeframe(state: TradingState, symbol: str) -> PredictionSignal:
    """
    Orchestrates the multi-timeframe prediction process.
    """
    predictor = ChronosPredictor()
    futures = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for timeframe in TIME_FRAMES:
            if timeframe in state.historical_data and not state.historical_data[timeframe].empty:
                price_series = state.historical_data[timeframe]['close']
                future = executor.submit(_predict_single_timeframe, timeframe, price_series, predictor)
                futures[future] = timeframe

    results = {}
    for future in concurrent.futures.as_completed(futures):
        timeframe, prediction, confidence = future.result()
        if confidence > CONFIDENCE_THRESHOLD:
            results[timeframe] = {"prediction": prediction, "confidence": confidence}

    fused_prediction, total_weight = 0.0, 0.0
    if results:
        for timeframe, res in results.items():
            weight = TIME_FRAME_WEIGHTS.get(timeframe, 0)
            fused_prediction += res["prediction"] * res["confidence"] * weight
            total_weight += res["confidence"] * weight

        if total_weight > 0:
            fused_prediction /= total_weight

    decision = "WAITING"
    if fused_prediction > 0.0005:
        decision = "LONG_ENTRY"
    elif fused_prediction < -0.0005:
        decision = "SHORT_ENTRY"

    gc.collect()

    return PredictionSignal(
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        symbol=symbol,
        fused_prediction_pct=fused_prediction * 100,
        confidence=total_weight / sum(TIME_FRAME_WEIGHTS.values()) if results else 0.0,
        decision=decision,
        details={tf: r["prediction"]*100 for tf, r in results.items()}
    )
