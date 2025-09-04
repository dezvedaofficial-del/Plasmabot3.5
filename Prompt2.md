# PlasmaTrader v3.0 - Núcleo Mínimo Ejecutivo
## Directriz para Desarrollo de Core Canónico Chronos-Bolt

### <executive_summary>
Desarrollar un núcleo mínimo de trading automatizado BTC/USDT que opere exclusivamente con **Chronos-Bolt** como motor predictivo canónico al 100%, complementado únicamente por análisis de microestructura de mercado para contexto en tiempo real. El sistema debe ser completamente autónomo, aparamétrico, y operar sin intervención del usuario más allá del inicio por CLI.

**Restricciones Técnicas Críticas**: Python 3.8+, CPU-only inference, sin dependencias de Docker/TensorFlow, máximo 500 líneas por archivo, manejo explícito de excepciones sin `except:` genérico.

### <core_architecture>

#### Módulos Mínimos Requeridos (Solo 6 archivos):
```
plasmatrader_core/
├── core_engine.py          # Orchestración principal y tipos de datos
│                           # Clases: TradingState, MarketData, PredictionSignal
│                           # Funciones: initialize_system(), main_trading_loop()
├── chronos_predictor.py    # Chronos-Bolt forecasting (100% señal)
│                           # Función principal: predict_multi_timeframe()
│                           # Clases: ChronosPredictor, PredictionCache
├── market_feed.py          # Binance WebSocket + microestructura básica
│                           # Clases: BinanceWebSocket, MarketMicrostructure
│                           # Funciones: connect_websocket(), handle_market_data()
├── risk_controller.py      # Kelly Criterion simplificado + drawdown
│                           # Funciones: calculate_position_size(), check_drawdown()
│                           # Clases: RiskManager, DrawdownTracker
├── paper_trader.py         # Ejecución de trades simulados realistas
│                           # Clases: PaperTradingEngine, Order, Position
│                           # Funciones: execute_order(), calculate_pnl()
└── cli_monitor.py          # Interface CLI + métricas esenciales
                            # Función principal: main(), display_dashboard()
                            # Clases: DashboardRenderer, MetricsCollector
```

#### Flujo de Datos Entre Módulos:
```
market_feed.py → core_engine.py → chronos_predictor.py → risk_controller.py → paper_trader.py
       ↓                ↓                    ↓                    ↓                ↓
   WebSocket      TradingState      PredictionSignal      PositionSize        Order
   MarketData   → MarketData    → + Confidence      → + RiskMetrics   → Execution
```

### <technical_specifications>

#### 1. **Chronos-Bolt Canónico (100% Señal)**
- **Modelo**: `amazon/chronos-bolt-medium` (24M parámetros)
- **Dependencias Exactas** (requirements.txt):
  ```
  transformers>=4.35.0,<5.0.0
  torch>=2.0.0,<3.0.0  # CPU-only: pip install torch --index-url https://download.pytorch.org/whl/cpu
  numpy>=1.24.0,<2.0.0
  pandas>=2.0.0,<3.0.0
  websocket-client>=1.6.0,<2.0.0
  requests>=2.31.0,<3.0.0
  ```
- **Instalación Verificada**: `pip install -r requirements.txt` debe completarse sin errores
- **Validación de Dependencias**: Verificar importaciones al inicio con manejo específico de `ImportError`
- **Configuración Máxima**:
  - Múltiples timeframes: 1m, 3m, 5m, 15m, 30m, 1h
  - Ventana histórica: exactamente 200 puntos por timeframe
  - Predicción multi-step: 1, 3, 5, 10, 15 pasos adelante
  - Ensemble de predicciones por timeframe con ponderación temporal
  - Intervalos de confianza: 80%, 90%, 95% para filtrado de señales
- **Optimización CPU**: 
  - Inferencia batch (max 6 timeframes simultáneos)
  - Cache de modelos en memoria (singleton pattern)
  - Cuantización int8 con `torch.quantization.quantize_dynamic()`
  - Thread pool para predicciones paralelas (max_workers=2)
  - Garbage collection explícito post-inferencia: `gc.collect()`
- **Explotación Avanzada**:
  - Cross-timeframe signal fusion con pesos: [0.1, 0.15, 0.2, 0.25, 0.15, 0.15]
  - Confidence-weighted predictions (threshold mínimo: 0.7)
  - Temporal decay weighting (factor: 0.95 por paso)
  - Volatility-adjusted forecasting (ventana móvil: 20 períodos)

#### 2. **Market Microstructure Mínima**
- **Datos Críticos**: Bid-ask spread, volumen tick, order book top 5 niveles
- **Endpoints Binance** (con fallbacks):
  - WebSocket Principal: `wss://stream.binance.com:9443/ws/btcusdt@ticker`
  - WebSocket Backup: `wss://stream.binance.com:443/ws/btcusdt@ticker`
  - Order Book: `wss://stream.binance.com:9443/ws/btcusdt@depth5@100ms`
  - Trades: `wss://stream.binance.com:9443/ws/btcusdt@trade`
  - REST API: `https://api.binance.com/api/v3/klines` (datos históricos)
  - **Timeout Configuración**: connect_timeout=10s, ping_interval=20s, ping_timeout=10s
- **Métricas Cuantificadas**:
  - Spread relativo: (ask-bid)/mid_price * 10000 (en basis points)
  - Presión de compra/venta: ratio volumen bid/ask (threshold: >1.2 para señal)
  - Liquidez instantánea: suma top 5 niveles (mínimo: $50,000 USD)
- **Función**: Filtro de calidad de señal (spread <10 bps) y timing de entrada/salida

#### 3. **Risk Controller Sofisticado-Simple**
- **Kelly Criterion Adaptativo**:
  - Cálculo: f* = (bp - q) / b, donde b=odds, p=win_rate, q=1-p
  - Win rate histórico: ventana móvil de 50 trades
  - Máximo 1.5% riesgo por trade (hard limit)
  - Ajuste volatilidad: factor = min(1.0, 0.02/realized_vol_20d)
- **Drawdown Protection**:
  - Stop total: 8.0% drawdown desde high water mark
  - Reducción progresiva: -25% posición cada 1% drawdown desde 5%
  - Recovery mode: máximo 0.5% riesgo por trade hasta nuevo high water mark
- **Validación de Órdenes**:
  - Tamaño mínimo: $10 USD
  - Tamaño máximo: $1000 USD (paper trading)
  - Verificación de balance antes de cada trade

#### 4. **Paper Trading Ultra-Realista**
- **Simulación Exacta**:
  - Slippage basado en spread real y volumen
  - Comisiones Binance futures exactas (0.02% maker, 0.04% taker)
  - Latencia simulada (50-200ms)
  - Partial fills en órdenes grandes
- **Tracking Preciso**:
  - PnL mark-to-market en tiempo real
  - Funding fees simulados cada 8 horas
  - Margin requirements dinámicos

### <data_ingestion_protocol>

#### Ingesta Inicial Crítica (Pre-Trading):
1. **Descarga histórica**: exactamente 1000 velas por timeframe vía REST API
   - Endpoint: `https://api.binance.com/api/v3/klines`
   - Parámetros: symbol=BTCUSDT, interval=[1m,3m,5m,15m,30m,1h], limit=1000
2. **Warm-up Chronos**: Pre-carga de modelo con primeras 800 velas, validación con últimas 200
3. **Baseline metrics**: 
   - Volatilidad: std(returns) * sqrt(periods_per_day) por timeframe
   - Correlaciones: matriz 6x6 entre timeframes (Pearson)
   - Spread promedio: media móvil 100 períodos del spread relativo
4. **Validación de conectividad**: 
   - Test ping a todos los endpoints WebSocket
   - Verificación de recepción de datos por 30 segundos
   - Validación de timestamps (tolerancia: ±2 segundos)
5. **Estado inicial**: Wallet virtual $10,000 USDT, posición neutral, PnL=0

**Tiempo estimado de ingesta**: 2-3 minutos (timeout: 5 minutos)
**Criterio de inicio**: 
- Exactamente 200 puntos válidos por timeframe (sin gaps)
- Conectividad estable (>95% mensajes recibidos en test)
- Modelos Chronos cargados y validados
- Spread promedio <20 basis points

### <cli_interface_specifications>

#### Métricas Esenciales en Pantalla:
```
┌─ PlasmaTrader v3.0 Core ─────────────────────────────┐
│ BTC/USDT: $43,247.82 ↗ (+0.34%)                     │
│                                                      │
│ Bot Decision: LONG ENTRY (Confidence: 87.3%)        │
│ └─ Chronos Signal: +2.1% (15m), +1.8% (30m)        │
│ └─ Entry Logic: Strong uptrend + low spread          │
│                                                      │
│ Active Position: LONG 0.023 BTC @ $43,180           │
│ Current P&L: +$1.56 (+0.016%)                       │
│                                                      │
│ Session Stats:                                       │
│ ├─ Total Trades: 47                                  │
│ ├─ Win Rate: 68.1%                                   │
│ ├─ Total P&L: +$127.34 (+1.27%)                     │
│ └─ Wallet Balance: $10,127.34 USDT                  │
│                                                      │
│ System: ●LIVE │ Feed: ●STABLE │ Risk: 23%           │
└──────────────────────────────────────────────────────┘
```

#### Estados de Bot Decision:
- `ANALYZING` - Procesando datos
- `LONG ENTRY` - Abriendo posición larga
- `SHORT ENTRY` - Abriendo posición corta  
- `POSITION HOLD` - Manteniendo posición
- `CLOSE POSITION` - Cerrando posición
- `RISK PAUSE` - Pausado por gestión de riesgo
- `WAITING` - Esperando condiciones favorables

### <operational_requirements>

#### Inicio Completamente Autónomo:
```bash
python cli_monitor.py
```
**Secuencia automática**:
1. Ingesta de datos inicial
2. Inicialización de Chronos-Bolt
3. Conexión a Binance WebSocket
4. Inicio de loop de trading automático
5. Display de métricas en tiempo real

#### Garantías de Estabilidad:
- **Auto-reconnect**: Reconexión automática con backoff exponencial (1s, 2s, 4s, 8s, max 60s)
- **Error recovery** (manejo específico por tipo):
  ```python
  try:
      # WebSocket operations
  except websocket.WebSocketConnectionClosedException:
      # Reconectar inmediatamente
  except ConnectionError as e:
      # Reintentar hasta 5 veces con backoff
  except TimeoutError as e:
      # Aumentar timeout y reintentar
  except json.JSONDecodeError as e:
      # Log error específico y continuar
  except KeyError as e:
      # Usar último valor válido, log missing key
  except Exception as e:
      # Log error completo y determinar si es recoverable
  ```
- **State persistence**: 
  - Archivo: `state.json` guardado cada 5 minutos + al cerrar posiciones
  - Formato exacto: 
    ```json
    {
      "timestamp": "2024-01-01T12:00:00Z",
      "wallet_balance": 10000.0,
      "positions": {
        "BTCUSDT": {"side": "LONG", "size": 0.023, "entry_price": 43180.0}
      },
      "total_pnl": 127.34,
      "trades": [{"timestamp": "...", "side": "BUY", "price": 43180.0, "size": 0.023, "pnl": 1.56}],
      "risk_metrics": {"current_drawdown": 0.02, "win_rate": 0.681}
    }
    ```
  - Backup rotativo: `state_backup_YYYYMMDD_HHMMSS.json` (últimas 24 horas)
  - Validación JSON al cargar con esquema predefinido
- **Graceful shutdown**: 
  - Captura SIGINT (Ctrl+C) y SIGTERM
  - Cierre ordenado: guardar estado → cerrar posiciones → desconectar WebSocket
  - Timeout máximo de shutdown: 30 segundos

#### Escalabilidad Futura:
- **Arquitectura modular**: Fácil adición de nuevos predictores
- **Interface estándar**: API interna para nuevos componentes
- **Data pipeline**: Preparado para múltiples fuentes de datos
- **Config system**: Base para futuras configuraciones

### <success_metrics>

#### Criterios de Éxito del Núcleo:
- **Operación autónoma**: 24+ horas sin intervención manual
- **Estabilidad**: <1% tiempo de inactividad (max 14.4 min/día)
- **Performance**: Sharpe ratio >1.0 en paper trading (252 días anualizados)
- **Eficiencia**: <4GB RAM pico, <70% CPU promedio, <100MB/hora tráfico red
- **Precisión**: >60% win rate en trades (mínimo 50 trades para validez estadística)
- **Latencia**: <500ms desde señal Chronos hasta orden generada
- **Recuperación**: <30s para reconectar tras desconexión de red

#### Validación Pre-Producción:
1. **Test de ingesta**: 
   - Criterio: 6000 velas históricas (1000 por timeframe) en <3 minutos
   - Validación específica:
     ```python
     # Sin gaps temporales
     assert all(timestamps[i+1] - timestamps[i] == expected_interval)
     # Precios válidos (no NaN, > 0, variación < 10% entre velas)
     assert all(0 < price < price_prev * 1.1 for price in prices)
     # Volúmenes positivos
     assert all(volume > 0 for volume in volumes)
     ```
2. **Test de predicción**: 
   - Criterio: Chronos genera predicciones válidas cada 60±5 segundos
   - Validación específica:
     ```python
     # Valores numéricos válidos
     assert not np.isnan(prediction).any() and not np.isinf(prediction).any()
     # Intervalos de confianza ordenados
     assert confidence_80 <= confidence_90 <= confidence_95
     # Predicciones dentro de rangos razonables (±20% precio actual)
     assert 0.8 * current_price <= prediction <= 1.2 * current_price
     ```
3. **Test de trading**: 
   - Criterio: 10 órdenes simuladas ejecutadas correctamente
   - Validación: cálculo PnL preciso, comisiones aplicadas, slippage simulado
4. **Test de resistencia**: 
   - Criterio: 48 horas continuas con <1% downtime
   - Métricas: memoria estable (<4GB), CPU <70%, reconexiones <10/hora
5. **Test de recovery**: 
   - Escenarios: desconexión WebSocket, corrupción de estado, reinicio forzado
   - Criterio: recuperación completa en <60 segundos, sin pérdida de datos críticos

### <implementation_directive>

**OBJETIVO**: Crear un núcleo de trading completamente funcional que demuestre el poder predictivo de Chronos-Bolt en su máxima expresión, con la mínima complejidad arquitectónica posible, listo para escalamiento orgánico futuro.

**PRIORIDAD ABSOLUTA**: 
1. Chronos-Bolt al máximo rendimiento
2. Ingesta de datos real y robusta  
3. Paper trading ultra-realista
4. CLI informativo y estable
5. Operación completamente autónoma

**RESTRICCIONES CRÍTICAS**:
- Solo datos reales de Binance (cero simulación/mocks)
- CPU únicamente, máximo 6GB RAM
- Cero configuración del usuario
- Inicio con un solo comando
- Arquitectura preparada para expansión futura

El sistema resultante debe ser el núcleo de trading automatizado más avanzado tecnológicamente posible usando Chronos-Bolt, manteniendo la simplicidad operacional y la robustez necesaria para operación 24/7 sin supervisión.

#### Principios Arquitectónicos:
- **Separación de Responsabilidades**: Cada módulo tiene una función específica y bien definida
- **Inversión de Dependencias**: Uso de interfaces abstractas para componentes intercambiables
- **Principio Abierto/Cerrado**: Extensible sin modificar código existente
- **Responsabilidad Única**: Cada clase/función tiene una sola razón para cambiar
- **Composición sobre Herencia**: Preferencia por composición de objetos

#### Validación y Calidad de Datos:
- **Integridad de Datos**:
  - Verificación de gaps en series temporales
  - Validación de rangos de precios (outlier detection)
  - Consistencia entre timeframes
- **Manejo de Datos Faltantes**:
  - Estrategias de interpolación para gaps menores
  - Re-fetch automático para gaps críticos
  - Alertas para inconsistencias mayores
- **Backup y Persistencia**:
  - Cache local de datos históricos
  - Backup incremental cada hora
  - Recovery automático desde último estado válido
- **Auditoría y Compliance**:
  - Log completo de todas las transacciones
  - Timestamps precisos con timezone UTC
  - Validación de balances en cada operación
  - Reportes de performance exportables

#### Garantías de Estabilidad Avanzadas:
- **Auto-reconnect**: Reconexión automática a WebSocket con backoff exponencial
- **Error recovery**: Continuación tras errores temporales con circuit breaker
- **State persistence**: Guardado automático de estado cada 5 minutos + checkpoints
- **Graceful shutdown**: Cierre limpio con Ctrl+C, SIGTERM, y cleanup completo
- **Automatic restart**: Reinicio automático tras fallos críticos
- **Estabilidad**: <1% tiempo de inactividad (máximo 14.4 min/día)
- **Performance**: Sharpe ratio >1.0 en paper trading (objetivo: 1.5+)
- **Eficiencia**: <4GB RAM, <70% CPU promedio (alertas en 80%)
- **Precisión**: >60% win rate en trades (objetivo: 65%+)
- **Latencia**: <100ms promedio para decisiones de trading
- **Throughput**: Procesamiento de >1000 señales/hora