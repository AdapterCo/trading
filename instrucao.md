# INSTRUCAO.MD

# PLATAFORMA DE TRADING AUTOMATIZADO — PRODUÇÃO / CAPITAL REAL

## 0. LEIA ANTES DE IMPLEMENTAR

Este arquivo é a especificação principal do projeto.

A IA/agente responsável pelo desenvolvimento deve seguir este documento rigorosamente.

Não preencher lacunas financeiras com suposições silenciosas.

Não alterar arquitetura, estratégia, parâmetros, tecnologias ou regras de risco sem autorização explícita.

Quando uma informação depender da exchange:

> consultar documentação/API oficial e atual.

Quando depender de configuração:

> utilizar configuração versionada.

Quando depender de mercado:

> utilizar dado real.

Quando um dado crítico estiver ausente, inconsistente ou desatualizado:

> NÃO ABRIR NOVA OPERAÇÃO.

Nunca inventar valores.

---

# 1. OBJETIVO

Construir uma plataforma profissional de trading automatizado capaz de operar dinheiro real continuamente.

A primeira versão operacional já deverá suportar produção real.

O sistema deverá:

* conectar à exchange;
* consultar conta e saldo;
* receber dados reais de mercado;
* construir/receber candles;
* calcular indicadores;
* executar estratégia determinística;
* gerar BUY/HOLD/EXIT;
* controlar risco;
* calcular tamanho da posição;
* enviar ordens reais;
* acompanhar ordens;
* processar partial fills;
* controlar posição;
* executar stop;
* executar take profit;
* executar trailing stop;
* contabilizar fees;
* medir slippage;
* calcular PnL;
* manter ledger auditável;
* reconciliar banco e exchange;
* sobreviver a restart;
* possuir kill switch;
* coletar dados permanentemente;
* possuir dashboard;
* operar 24/7 em VPS.

O capital inicial pretendido é aproximadamente R$100 convertidos para USDT.

Nunca utilizar R$100 hardcoded.

Sempre trabalhar com saldo real disponível.

A arquitetura deve permitir aumento futuro de capital sem reescrever o núcleo financeiro.

---

# 2. PRINCÍPIO FUNDAMENTAL

Separar obrigatoriamente:

```text
MARKET DATA
    ↓
STRATEGY
    ↓
SIGNAL
    ↓
RISK
    ↓
ORDER INTENT
    ↓
EXECUTION
    ↓
EXCHANGE ORDER
    ↓
FILL
    ↓
POSITION
    ↓
LEDGER
    ↓
METRICS
```

StrategyEngine NÃO envia ordens.

RiskEngine NÃO gera sinais.

ExchangeAdapter NÃO decide estratégia.

Cada componente deve possuir responsabilidade claramente separada.

---

# 3. MERCADO INICIAL

Exchange:

```text
Binance
```

Mercado:

```text
SPOT
```

Par inicial:

```text
BTCUSDT
```

Quote asset:

```text
USDT
```

Base asset:

```text
BTC
```

---

# 4. RESTRIÇÕES DA V1

A V1 utilizará:

```text
1 exchange
1 símbolo
1 estratégia
1 posição simultânea
Spot
Long Only
sem margem
sem futuros
sem alavancagem
sem short
sem saque
```

SELL significa vender BTC anteriormente adquirido pelo sistema.

SELL nunca significa abrir short.

---

# 5. MODOS

Implementar:

```env
TRADING_MODE=research
TRADING_MODE=paper
TRADING_MODE=testnet
TRADING_MODE=live
```

Todos devem compartilhar o mesmo:

```text
MarketDataEngine
StrategyEngine
RiskEngine
PositionEngine
MetricsEngine
```

A principal diferença deve estar na camada de execução.

```text
paper
→ PaperExecutionAdapter

testnet
→ ExchangeTestnetAdapter

live
→ ExchangeLiveAdapter
```

A aplicação poderá ser implantada diretamente em:

```env
TRADING_MODE=live
```

quando configurada explicitamente pelo operador.

Nunca utilizar LIVE como default.

`.env.example` nunca deverá vir com LIVE habilitado.

---

# 6. STACK

Backend:

```text
Python
FastAPI
Pydantic
SQLAlchemy
Alembic
```

Banco:

```text
PostgreSQL
```

Frontend:

```text
React
TypeScript
Vite
TailwindCSS
```

Infraestrutura:

```text
Docker
Docker Compose
Nginx ou Traefik
VPS
```

Processamento:

```text
Decimal → financeiro
NumPy float64 → pesquisa estatística
```

Exchange:

```text
ExchangeAdapter
```

A biblioteca concreta da Binance deve ser escolhida verificando documentação e manutenção atuais.

Não presumir que uma biblioteca antiga continua sendo a melhor opção.

---

# 7. ESTRUTURA CONCEITUAL

Implementar:

```text
MarketDataEngine
StrategyEngine
RiskEngine
ExecutionEngine
ExchangeAdapter
PositionEngine
LedgerEngine
MetricsEngine
ReconciliationEngine
SafetyEngine
FeatureEngine
AlertService
```

Além de:

```text
API
Dashboard
PostgreSQL
worker-execution
worker-market-data
```

---

# 8. PRECISÃO FINANCEIRA

Tudo relacionado a:

```text
saldo
preço
quantidade
fee
PnL
posição
ordem
ledger
capital
risco
```

deve utilizar:

```python
Decimal
```

Configurar explicitamente:

```python
getcontext().prec = 28
```

Não converter silenciosamente Decimal para float.

Float poderá ser utilizado em processamento estatístico onde precisão contábil exata não for necessária.

---

# 9. TIMEFRAMES

Base de coleta:

```text
1m
```

Entrada:

```text
5m
```

Tendência:

```text
15m
```

Contexto macro:

```text
1h
```

Configuração:

```env
BASE_INTERVAL=1m
ENTRY_INTERVAL=5m
TREND_INTERVAL=15m
MACRO_INTERVAL=1h
```

---

# 10. MARKET DATA ENGINE

Criar:

```text
MarketDataEngine
```

Responsável por:

* histórico;
* WebSocket;
* candles;
* timestamps;
* validação;
* gaps;
* reconexão;
* dados stale;
* normalização.

Dados utilizados pela StrategyEngine devem possuir formato consistente.

---

# 11. CANDLE FECHADO

A StrategyEngine somente poderá decidir utilizando:

```text
CLOSED CANDLE
```

Nunca utilizar OHLC final de candle ainda aberto.

Fluxo:

```text
OPEN
↓
UPDATES
↓
CLOSED
↓
STRATEGY
```

---

# 12. HISTÓRICO E WARMUP

Antes da estratégia funcionar:

```text
LOAD HISTORICAL DATA
```

Como EMA200 é utilizada, carregar histórico suficiente para inicializar corretamente todos os indicadores.

Nunca preencher candles faltantes com valores inventados.

Enquanto o warmup estiver incompleto:

```text
STRATEGY_READY = FALSE
```

---

# 13. STRATEGY V1

Nome:

```text
TrendPullbackV1
```

Tipo:

```text
Trend Following + Pullback
Long Only
```

Objetivo:

identificar tendência positiva, aguardar correção e entrar quando houver confirmação de retomada.

Interface:

```python
class Strategy:
    def on_candle(self, candle, context) -> Signal:
        ...
```

Possíveis decisões:

```text
BUY
HOLD
EXIT
```

---

# 14. INDICADORES

Implementar:

```text
EMA 20
EMA 50
EMA 200

RSI 14

ATR 14

ADX 14

Volume SMA 20
```

Também calcular:

```text
return_1
return_3
return_12

volume_ratio

taker_buy_ratio

spread
```

Criar testes automatizados para os cálculos.

---

# 15. FILTRO MACRO — 1H

Long somente permitido quando:

```text
close_1h > EMA200_1h
```

E:

```text
EMA50_1h > EMA200_1h
```

Caso contrário:

```text
ALLOW_LONG = FALSE
```

---

# 16. TENDÊNCIA — 15M

Exigir:

```text
EMA20_15m > EMA50_15m
```

E:

```text
close_15m > EMA50_15m
```

Caso contrário:

```text
BUY = BLOCKED
```

---

# 17. ADX

Indicador:

```text
ADX(14)
```

Timeframe:

```text
15m
```

Configuração:

```env
ADX_MIN=20
```

Exigir:

```text
ADX_15m >= 20
```

ADX mede força.

Não utilizar ADX para determinar direção.

---

# 18. PULLBACK

Timeframe:

```text
5m
```

Calcular:

```text
distance_to_ema20 =
abs(close - EMA20) / EMA20
```

Configuração:

```env
PULLBACK_MAX_DISTANCE=0.003
```

equivalente a:

```text
0,30%
```

Exigir:

```text
distance_to_ema20 <= 0.003
```

---

# 19. RSI

Indicador:

```text
RSI(14)
```

Timeframe:

```text
5m
```

Configuração:

```env
RSI_ENTRY_MIN=45
RSI_ENTRY_MAX=65
```

Exigir:

```text
45 <= RSI <= 65
```

Não implementar:

```text
RSI < 30 → BUY
```

como estratégia isolada.

---

# 20. CONFIRMAÇÃO

Depois do pullback exigir:

```text
close_5m > previous_close_5m
```

E:

```text
close_5m > EMA20_5m
```

Sempre utilizar candle fechado.

---

# 21. VOLUME

Calcular:

```text
volume_ratio =
current_volume /
SMA(volume,20)
```

Configuração:

```env
MIN_VOLUME_RATIO=1.0
```

Exigir:

```text
volume_ratio >= 1.0
```

---

# 22. TAKER BUY RATIO

Calcular quando os dados necessários estiverem disponíveis:

```text
taker_buy_ratio =
taker_buy_quote_volume /
total_quote_volume
```

Configuração:

```env
MIN_TAKER_BUY_RATIO=0.50
```

Exigir:

```text
taker_buy_ratio >= 0.50
```

Se o dado necessário estiver indisponível ou inválido:

```text
NO TRADE
```

Nunca inventar valor.

---

# 23. SPREAD

Antes da ordem consultar:

```text
best_bid
best_ask
```

Calcular:

```text
mid_price =
(best_bid + best_ask) / 2
```

```text
spread =
(best_ask - best_bid) /
mid_price
```

Configuração inicial:

```env
MAX_SPREAD=0.001
```

equivalente a:

```text
0,10%
```

Se:

```text
spread > MAX_SPREAD
```

então:

```text
NO TRADE
```

---

# 24. REGRA COMPLETA DE BUY

BUY somente quando TODAS forem verdadeiras.

## 1H

```text
close > EMA200
EMA50 > EMA200
```

## 15M

```text
EMA20 > EMA50
close > EMA50
ADX >= 20
```

## 5M

```text
distance_to_EMA20 <= 0.30%
RSI >= 45
RSI <= 65
close > EMA20
close > previous_close
volume_ratio >= 1.0
taker_buy_ratio >= 0.50
```

## EXECUÇÃO

```text
spread <= MAX_SPREAD
market data healthy
exchange connected
account synchronized
balance available
no existing position
no conflicting order
cooldown inactive
RiskEngine approved
daily loss not reached
drawdown not reached
consecutive loss limit not reached
```

Somente então:

```text
Signal = BUY
```

Caso contrário:

```text
Signal = HOLD
```

---

# 25. SIGNAL

Signal deve registrar:

```text
id
timestamp
symbol
strategy
strategy_version
decision
reference_price
candle_id
reasons
indicator_snapshot
```

BUY deve possuir razões positivas.

HOLD deve registrar razões que impediram entrada.

EXIT deve registrar motivo.

---

# 26. STOP LOSS

Base:

```text
ATR(14) 5m
```

Configuração:

```env
STOP_ATR_MULTIPLIER=1.5
```

Calcular:

```text
stop_distance =
ATR_5m × 1.5
```

Então:

```text
stop_price =
entry_price - stop_distance
```

Limite:

```env
MAX_STOP_PERCENT=0.02
```

equivalente a:

```text
2%
```

Se o stop natural exigir mais de 2%:

```text
NO TRADE
```

Não apertar artificialmente o stop.

---

# 27. RISCO POR OPERAÇÃO

Configuração inicial:

```env
RISK_PER_TRADE=0.01
```

equivalente a:

```text
1%
```

Calcular:

```text
risk_amount =
equity × risk_per_trade
```

Risco significa perda planejada até o stop.

Não significa tamanho da posição.

---

# 28. POSITION SIZING

Calcular:

```text
risk_per_unit =
entry_price - stop_price
```

Então:

```text
quantity_by_risk =
risk_amount /
risk_per_unit
```

Depois limitar por:

```text
saldo
MAX_CAPITAL_ALLOCATION
minQty
maxQty
stepSize
minNotional
maxNotional quando aplicável
```

O RiskEngine deverá utilizar o menor limite permitido.

---

# 29. CAPITAL MÁXIMO ALOCADO

Configuração:

```env
MAX_CAPITAL_ALLOCATION=0.95
```

Máximo:

```text
95%
```

do saldo elegível.

Manter margem para:

```text
fees
rounding
execution differences
```

---

# 30. TAKE PROFIT

Configuração:

```env
TAKE_PROFIT_R=2.0
```

Definir:

```text
R =
entry_price - stop_price
```

Então:

```text
take_profit =
entry_price + (2 × R)
```

Risco/retorno inicial:

```text
1:2
```

---

# 31. BREAK-EVEN

Configuração:

```env
BREAK_EVEN_TRIGGER_R=1.0
```

Quando:

```text
price >= entry + 1R
```

ativar proteção de break-even.

Break-even econômico deve considerar:

```text
fees
slippage observado
```

Não assumir:

```text
stop = entry
```

como lucro líquido zero automaticamente.

---

# 32. TRAILING STOP

Configuração:

```env
TRAILING_START_R=1.5
TRAILING_ATR_MULTIPLIER=1.0
```

Ativar quando:

```text
price >= entry + 1.5R
```

Depois:

```text
trailing_stop =
highest_price_since_entry -
ATR_5m
```

O trailing stop somente pode:

```text
SUBIR
```

Nunca afastar stop aumentando risco.

---

# 33. SAÍDA ESTRATÉGICA

No candle fechado de 5m:

```text
close < EMA50_5m
```

E:

```text
EMA20_5m < EMA50_5m
```

Então:

```text
EXIT
```

---

# 34. PRIORIDADE DE SAÍDA

Prioridade:

```text
EMERGENCY
↓
STOP
↓
TAKE PROFIT
↓
TRAILING
↓
STRATEGY EXIT
```

Nunca permitir duas rotinas venderem a mesma quantidade.

Implementar controle idempotente de saída.

---

# 35. UMA POSIÇÃO

Configuração:

```env
MAX_OPEN_POSITIONS=1
```

Enquanto houver posição:

```text
NEW BUY = BLOCKED
```

Registrar motivo.

---

# 36. COOLDOWN

Configuração:

```env
COOLDOWN_CANDLES=2
```

Depois de uma posição fechar:

```text
aguardar 2 candles de 5m
```

antes de permitir nova entrada.

---

# 37. PERDAS CONSECUTIVAS

Configuração:

```env
MAX_CONSECUTIVE_LOSSES=3
```

Ao atingir:

```text
BLOCK_NEW_ENTRIES
```

Default:

```text
MANUAL_RESUME_REQUIRED
```

---

# 38. PERDA DIÁRIA

Configuração:

```env
MAX_DAILY_LOSS=0.03
```

equivalente a:

```text
3%
```

do equity de referência do início do ciclo diário.

Ao atingir:

```text
BLOCK_NEW_ENTRIES
```

Não liquidar automaticamente posição existente por causa desse limite.

A posição continua obedecendo suas proteções.

---

# 39. DRAWDOWN

Configuração:

```env
MAX_DRAWDOWN=0.10
```

equivalente a:

```text
10%
```

sobre high-water mark.

Ao atingir:

```text
BOT = PAUSED
MANUAL_RESUME_REQUIRED
```

---

# 40. LIMITES OPERACIONAIS

Configuração:

```env
MAX_ORDERS_PER_HOUR=6
MAX_ENTRIES_PER_DAY=10
```

São limites.

Não são metas.

O robô não deve procurar operações somente para atingir quantidade.

Zero trades em determinado período é válido.

---

# 41. RISK ENGINE

Implementar:

```text
RiskEngine
```

Responsável por:

```text
risk_per_trade
position_size
max_capital_allocation
daily_loss
drawdown
consecutive_losses
open_positions
order_frequency
spread
market_data_health
exchange_health
balance
symbol_rules
```

Strategy pode retornar BUY.

RiskEngine pode retornar:

```text
REJECTED
```

A decisão do RiskEngine é final.

---

# 42. ORDER INTENT

Antes de enviar ordem criar:

```text
OrderIntent
```

Campos:

```text
id
signal_id
strategy_version
config_version
symbol
side
order_type
quantity
expected_price
stop_price
take_profit
risk_amount
created_at
status
```

OrderIntent NÃO significa ordem existente na exchange.

---

# 43. REGRAS DO SÍMBOLO

Nunca hardcode:

```text
tickSize
stepSize
minQty
maxQty
minNotional
maxNotional
```

ou equivalentes.

Buscar regras atuais da exchange.

Aplicar arredondamento conforme regras reais do símbolo.

Não usar `round()` arbitrariamente para quantidade/preço.

---

# 44. FEES

Não utilizar fee hardcoded como verdade absoluta.

Quando possível consultar comissão aplicável à conta.

Registrar fee efetivamente cobrada em cada fill.

Campos:

```text
commission
commission_asset
```

Resultado relevante:

```text
NET PNL
```

---

# 45. CLIENT ORDER ID

Toda ordem deverá possuir:

```text
client_order_id
```

único.

Persistir ANTES do envio quando necessário para idempotência.

---

# 46. TIMEOUT DE ORDEM

É proibido:

```text
SEND
↓
TIMEOUT
↓
SEND AGAIN
```

Implementar:

```text
SEND
↓
TIMEOUT
↓
QUERY client_order_id
↓
EXISTS?
├── YES → RECONCILE
└── NO → SAFE RETRY POLICY
```

Nunca duplicar ordem por retry.

---

# 47. ESTADOS DA ORDEM

Suportar:

```text
NEW
PARTIALLY_FILLED
FILLED
CANCELED
REJECTED
EXPIRED
```

E outros estados oficiais necessários que a exchange atualmente utilizar.

Não considerar HTTP 200 sinônimo de fill.

---

# 48. FILLS

Uma ordem pode gerar:

```text
Fill 1
Fill 2
Fill 3
...
```

Cada fill:

```text
exchange_trade_id
exchange_order_id
price
quantity
commission
commission_asset
timestamp
```

Preço médio:

```text
Σ(price × quantity)
────────────────────
Σ(quantity)
```

---

# 49. PARTIAL FILL

Nunca assumir execução total.

PositionEngine deve utilizar somente:

```text
executed_quantity
```

Proteções devem acompanhar a quantidade efetivamente adquirida.

Nunca tentar vender quantidade não executada.

---

# 50. POSITION ENGINE

Criar:

```text
PositionEngine
```

Responsável por:

```text
quantity
average_entry
cost_basis
fees
current_price
market_value
realized_pnl
unrealized_pnl
stop
take
trailing
```

Posição deriva de fills.

Não deriva somente de OrderIntent.

---

# 51. PROTEÇÃO DA POSIÇÃO

Após fill:

```text
UPDATE POSITION
↓
CALCULATE ACTUAL ENTRY
↓
UPDATE STOP
↓
UPDATE TAKE
↓
PROTECT POSITION
```

Proteção de posição possui prioridade sobre procura de novas entradas.

---

# 52. EXECUTION ENGINE

Criar processo independente:

```text
worker-execution
```

Nunca executar loop principal dentro de request FastAPI.

Loop conceitual:

```text
MARKET DATA
↓
CLOSED CANDLE
↓
STRATEGY
↓
SIGNAL
↓
RISK
↓
ORDER INTENT
↓
EXECUTION
↓
ORDER
↓
FILLS
↓
POSITION
↓
PROTECTION
↓
LEDGER
↓
METRICS
↓
RECONCILIATION
```

---

# 53. EXCHANGE ADAPTER

StrategyEngine nunca importa diretamente SDK/biblioteca da Binance.

Criar interface:

```text
ExchangeAdapter
```

Responsabilidades:

```text
get_server_time
get_account
get_balances
get_symbol_info
get_commissions
get_best_bid_ask
get_open_orders
get_order
get_recent_orders
get_trades
create_order
cancel_order
market_data
user_data
```

Métodos concretos devem respeitar a API atual.

---

# 54. LEDGER

Criar:

```text
ledger_entries
```

Eventos possíveis:

```text
BUY
SELL
FEE
REALIZED_PNL
ADJUSTMENT
```

Ledger é imutável.

Nunca editar lançamento histórico para esconder erro.

Correção:

```text
ORIGINAL ENTRY
+
ADJUSTMENT ENTRY
```

---

# 55. RECONCILIAÇÃO

A exchange é fonte autoritativa do estado externo.

No boot:

```text
START
↓
BLOCK TRADING
↓
GET ACCOUNT
↓
GET BALANCE
↓
GET OPEN ORDERS
↓
GET RECENT ORDERS
↓
GET FILLS
↓
COMPARE DATABASE
↓
RECONCILE
↓
CONSISTENT?
├── YES → CONTINUE
└── NO → BLOCK
```

Nunca abrir posição antes da reconciliação.

---

# 56. RECONCILIAÇÃO PERIÓDICA

Reconciliar periodicamente:

```text
balances
open orders
fills
position
```

Registrar:

```text
reconciliation_log
```

com:

```text
timestamp
type
internal_state
exchange_state
difference
resolution
status
```

---

# 57. USER DATA STREAM

Quando disponibilizado pela exchange, utilizar stream autenticado para:

```text
account updates
balance updates
order updates
execution updates
```

Stream em tempo real NÃO substitui reconciliação periódica.

Reconciliação periódica NÃO substitui stream em tempo real.

Utilizar ambos.

---

# 58. STARTUP LIVE

Sequência obrigatória:

```text
START

↓
LOAD CONFIG

↓
VALIDATE ENVIRONMENT

↓
VALIDATE SECRETS

↓
CONNECT DATABASE

↓
CONNECT EXCHANGE

↓
VERIFY API ACCESS

↓
VERIFY TRADING PERMISSION

↓
VERIFY WITHDRAWAL DISABLED
quando verificável

↓
VERIFY TIME

↓
LOAD SYMBOL RULES

↓
LOAD COMMISSION INFORMATION

↓
GET ACCOUNT

↓
GET BALANCES

↓
GET OPEN ORDERS

↓
GET RECENT FILLS

↓
RECONCILE

↓
CONNECT MARKET DATA

↓
CONNECT USER DATA

↓
LOAD HISTORICAL CANDLES

↓
WARM INDICATORS

↓
VERIFY DATA HEALTH

↓
INITIALIZE RISK ENGINE

↓
STRATEGY_READY

↓
TRADING_READY
```

Se qualquer etapa crítica falhar:

```text
NO NEW ORDERS
```

---

# 59. ESTADOS DO BOT

Implementar máquina explícita:

```text
STARTING
RECONCILING
WARMING_UP
READY
RUNNING
PAUSED
BLOCKED
DEGRADED
EMERGENCY
STOPPED
```

Toda transição deve ser registrada.

---

# 60. MARKET DATA STALE

Implementar:

```env
STALE_MARKET_DATA_TIMEOUT=<configurável>
```

O valor concreto deverá ser apropriado aos streams utilizados.

Se dados necessários estiverem stale:

```text
NO NEW ORDERS
```

Se houver posição aberta:

```text
priorizar recuperação do estado e proteção
```

---

# 61. TIME SYNC

A VPS deve possuir relógio sincronizado.

Antes de chamadas assinadas verificar compatibilidade temporal quando necessário.

Problemas relevantes de timestamp:

```text
BOT = DEGRADED
NO NEW ORDERS
```

até resolução.

---

# 62. PAUSE

Botão:

```text
PAUSE
```

deve:

```text
bloquear novas entradas
cancelar ordens pendentes de entrada quando seguro
preservar posição existente
preservar proteção da posição
```

PAUSE NÃO significa abandonar posição.

---

# 63. EMERGENCY EXIT

Comando separado:

```text
EMERGENCY EXIT
```

deve:

```text
cancelar ordens conflitantes
determinar posição real
fechar exposição conforme política configurada
confirmar execução
reconciliar
bloquear novas entradas
registrar evento
```

Nunca presumir que a posição fechou apenas porque a requisição foi enviada.

---

# 64. KILL SWITCH

Endpoint crítico deve permanecer simples e prioritário.

Exige autenticação.

Não depender de processamento pesado do dashboard.

---

# 65. RECUPERAÇÃO DE FALHAS

Testar:

```text
internet cai
WebSocket cai
user stream cai
exchange timeout
HTTP 429
HTTP 5xx
API reinicia
worker reinicia
PostgreSQL reinicia
partial fill
order rejected
order externally canceled
balance externally changed
market data stale
duplicate response
```

Regra:

```text
UNKNOWN STATE
↓
BLOCK NEW ORDERS
↓
RECONCILE
↓
VALIDATE
↓
RESUME
```

---

# 66. DATA COLLECTOR

Criar processo independente:

```text
worker-market-data
```

Rodar 24/7 independentemente de haver operação.

Dados coletados não dependem da Strategy gerar BUY.

---

# 67. HISTORICAL DATA IMPORTER

Criar:

```text
HistoricalDataImporter
```

Fonte primária:

```text
dados oficiais da exchange
```

Importar BTCUSDT.

Base:

```text
1m
```

Validar:

```text
duplicatas
gaps
timestamps
ordenação
```

Nunca alterar candle para melhorar estratégia.

---

# 68. MARKET DATA DATABASE

Armazenar pelo menos:

```text
symbol
interval
open_time
close_time

open
high
low
close

volume
quote_volume

trade_count

taker_buy_base_volume
taker_buy_quote_volume

source
received_at
```

Constraint:

```text
UNIQUE(symbol, interval, open_time)
```

---

# 69. MICROESTRUTURA

Coletar quando apropriado:

```text
best_bid
best_ask
mid_price
spread
bid_quantity
ask_quantity
```

Arquitetura deverá permitir futuramente:

```text
order book snapshots
depth
imbalance
```

Não armazenar indefinidamente cada evento de order book sem política de retenção.

---

# 70. FEATURE ENGINE

Criar:

```text
FeatureEngine
```

Features iniciais:

```text
return_1
return_3
return_12

EMA20
EMA50
EMA200

RSI14
ATR14
ADX14

distance_ema20
distance_ema50
distance_ema200

volume_ratio
taker_buy_ratio

spread
volatility
```

Dados derivados podem ser recalculados.

Preservar dados brutos.

---

# 71. DECISION LOG

Registrar TODA avaliação da estratégia.

Inclusive:

```text
HOLD
```

Tabela:

```text
strategy_decisions
```

Campos:

```text
timestamp
symbol
strategy
strategy_version
config_version

market_price

trend_1h
trend_15m

ema20
ema50
ema200

rsi
atr
adx

volume_ratio
taker_buy_ratio
spread

decision
rejection_reasons
```

Exemplo:

```json
{
  "decision": "HOLD",
  "rejection_reasons": [
    "ADX_BELOW_MINIMUM",
    "VOLUME_NOT_CONFIRMED"
  ]
}
```

---

# 72. MACHINE LEARNING — PREPARAÇÃO

A arquitetura deverá coletar dados suficientes para treinamento futuro.

ML não controla diretamente Strategy V1.

Preparar:

```text
MLSignalProvider
```

mas mantê-lo desativado inicialmente.

---

# 73. DATASET DE ML

Permitir gerar:

```text
X(t)
```

com features conhecidas em `t`.

Targets futuros poderão incluir:

```text
return_5m
return_15m
return_30m
return_1h
```

E classificações:

```text
UP
NEUTRAL
DOWN
```

Targets devem considerar posteriormente:

```text
fees
spread
slippage
```

para que pequeno movimento positivo não seja confundido com oportunidade economicamente positiva.

---

# 74. PROIBIÇÃO DE DATA LEAKAGE

Features em:

```text
t
```

somente podem utilizar informação disponível até:

```text
t
```

Targets podem olhar para o futuro porque representam o que será previsto.

Nunca permitir informação futura dentro das features.

---

# 75. MODELOS FUTUROS

Todo modelo deverá possuir:

```text
model_id
model_version
training_dataset
dataset_hash
feature_schema
training_period
validation_period
metrics
artifact_hash
created_at
```

Modelo não versionado nunca poderá participar de produção.

---

# 76. NÃO AUTO-OTIMIZAR

O robô NÃO poderá alterar sozinho:

```text
EMA
RSI
ADX
ATR
stop
take
risk
timeframe
volume filter
spread filter
```

porque ganhou ou perdeu recentemente.

Toda mudança:

```text
VERSIONADA
AUDITÁVEL
DELIBERADA
```

---

# 77. SLIPPAGE REAL

Antes da ordem registrar:

```text
expected_price
```

Depois dos fills calcular:

```text
executed_vwap
```

Então:

```text
realized_slippage
```

Armazenar histórico.

Posteriormente utilizar dados reais para melhorar:

```text
RiskEngine
BacktestExecutionModel
```

---

# 78. METRICS ENGINE

Calcular:

```text
initial_equity
current_equity

gross_profit
gross_loss

net_profit

return_percent

realized_pnl
unrealized_pnl

daily_pnl

fees
slippage

win_rate
loss_rate

average_win
average_loss

expectancy
profit_factor

payoff

max_drawdown

consecutive_wins
consecutive_losses

trade_count
```

Quando estatisticamente apropriado:

```text
Sharpe
Sortino
Calmar
```

Nunca esconder custos.

---

# 79. EQUITY

Definir de forma consistente:

```text
equity =
cash/quote balance
+
market value of assets controlled by bot
```

Evitar dupla contagem.

Documentar exatamente quais ativos pertencem ao escopo do robô.

---

# 80. HIGH-WATER MARK

Persistir:

```text
high_water_mark
```

Não resetar em restart.

Utilizar para drawdown.

---

# 81. DAILY REFERENCE EQUITY

Persistir equity de referência para cálculo do limite diário.

Não recalcular convenientemente após perdas.

Registrar mudança de ciclo.

---

# 82. BANCO DE DADOS

Criar pelo menos:

```text
users

strategies
strategy_versions
config_versions

market_data

strategy_decisions
signals

order_intents
exchange_orders
fills

positions
trades

ledger_entries

execution_state

reconciliation_log

risk_events

simulation_runs
monte_carlo_runs
backtests

settings
```

---

# 83. STRATEGY VERSION

Toda alteração de regra da estratégia:

```text
NEW STRATEGY VERSION
```

Cada operação deve apontar para:

```text
strategy_version
```

---

# 84. CONFIG VERSION

Alterações de parâmetros operacionais relevantes:

```text
NEW CONFIG VERSION
```

Cada operação deverá apontar para configuração utilizada.

---

# 85. AUDITORIA

Para qualquer trade deve ser possível responder:

```text
qual candle gerou a decisão?
qual estratégia?
qual versão?
quais indicadores?
qual sinal?
qual risco?
qual equity?
qual stop?
qual take?
qual quantidade?
qual OrderIntent?
qual client_order_id?
qual exchange_order_id?
quais fills?
qual preço médio?
quais fees?
qual slippage?
qual saída?
qual PnL?
```

---

# 86. HEARTBEAT

Workers deverão registrar:

```text
last_heartbeat
```

Dashboard deverá identificar worker morto.

---

# 87. OBSERVABILIDADE

Monitorar:

```text
worker_status
worker_uptime

exchange_connection
market_stream_status
user_stream_status

last_market_data
last_candle
last_strategy_run
last_signal

last_order
last_fill

last_reconciliation

exchange_latency
api_error_count
```

---

# 88. DASHBOARD

Mostrar:

```text
BOT STATUS
TRADING MODE

EXCHANGE STATUS
MARKET DATA STATUS
USER STREAM STATUS

BTC PRICE

USDT BALANCE
BTC BALANCE
BOT EQUITY

POSITION STATUS
QUANTITY
AVERAGE ENTRY
CURRENT PRICE
STOP
TAKE
TRAILING

REALIZED PNL
UNREALIZED PNL
DAILY PNL
TOTAL PNL

FEES
SLIPPAGE

WIN RATE
EXPECTANCY
PROFIT FACTOR
DRAWDOWN

CONSECUTIVE LOSSES

LAST SIGNAL
LAST ORDER
LAST FILL
LAST RECONCILIATION

RISK STATUS
```

---

# 89. CONTROLES DO DASHBOARD

Implementar:

```text
START
PAUSE
RESUME
EMERGENCY EXIT
```

Ações críticas exigem autenticação.

Nunca permitir botão público controlar capital real.

---

# 90. ALERT SERVICE

Criar:

```text
AlertService
```

Eventos:

```text
BOT BLOCKED
BOT PAUSED
EMERGENCY

ORDER REJECTED
ORDER ERROR

RECONCILIATION ERROR

MARKET DATA LOST
USER STREAM LOST

DATABASE ERROR

DAILY LOSS LIMIT
DRAWDOWN LIMIT

CONSECUTIVE LOSS LIMIT
```

Falha no AlertService não pode quebrar proteção financeira.

---

# 91. SEGURANÇA

API key:

```text
SPOT TRADING = ENABLED
WITHDRAWAL = DISABLED
```

Quando suportado:

```text
IP WHITELIST = VPS IP
```

Nunca implementar:

```text
withdraw
transfer out
```

---

# 92. CREDENCIAIS

Nunca colocar secrets em:

```text
Git
frontend
logs
responses
exceptions
database plaintext
```

`.env`:

```text
fora do Git
```

Credenciais armazenadas devem utilizar proteção adequada.

---

# 93. AUTENTICAÇÃO

Endpoints críticos:

```text
start
pause
resume
emergency_exit
settings
live controls
```

exigem autenticação.

---

# 94. CONFIGURAÇÃO DEFAULT V1

Centralizar:

```env
SYMBOL=BTCUSDT

BASE_INTERVAL=1m
ENTRY_INTERVAL=5m
TREND_INTERVAL=15m
MACRO_INTERVAL=1h

RISK_PER_TRADE=0.01
MAX_CAPITAL_ALLOCATION=0.95

MAX_DAILY_LOSS=0.03
MAX_DRAWDOWN=0.10
MAX_CONSECUTIVE_LOSSES=3

ADX_MIN=20

RSI_ENTRY_MIN=45
RSI_ENTRY_MAX=65

PULLBACK_MAX_DISTANCE=0.003

MIN_VOLUME_RATIO=1.0
MIN_TAKER_BUY_RATIO=0.50

MAX_SPREAD=0.001

STOP_ATR_MULTIPLIER=1.5
MAX_STOP_PERCENT=0.02

TAKE_PROFIT_R=2.0

BREAK_EVEN_TRIGGER_R=1.0

TRAILING_START_R=1.5
TRAILING_ATR_MULTIPLIER=1.0

COOLDOWN_CANDLES=2

MAX_OPEN_POSITIONS=1

MAX_ORDERS_PER_HOUR=6
MAX_ENTRIES_PER_DAY=10
```

Não espalhar números mágicos pelo código.

---

# 95. TESTES AUTOMATIZADOS

Obrigatórios para:

```text
EMA
RSI
ATR
ADX

position sizing

PnL
fees
slippage

drawdown
daily loss

expectancy
profit factor

Decimal precision

tick size
step size

idempotency

partial fills

reconciliation

risk limits

look-ahead/data leakage

cooldown

consecutive losses

stop

take

trailing
```

---

# 96. TESTES DE FALHA

Criar cenários deliberados:

```text
internet loss
WebSocket disconnect
user stream disconnect
exchange timeout
429
500
database disconnect
worker restart
API restart
partial fill
rejected order
canceled order
duplicate event
stale market data
balance mismatch
position mismatch
```

Sistema deve falhar de maneira segura.

---

# 97. BACKTEST ENGINE

Também implementar posteriormente:

```text
BacktestEngine
```

Deve utilizar exatamente a mesma:

```text
TrendPullbackV1
```

Não criar regras diferentes para histórico.

---

# 98. BACKTEST EXECUTION MODEL

Criar:

```text
BacktestExecutionModel
```

Considerar:

```text
fees
spread
slippage
tick size
step size
min notional
market execution
```

Não assumir execução perfeita.

---

# 99. PROIBIÇÃO DE LOOK-AHEAD

Ao decidir no candle:

```text
N
```

somente utilizar informações disponíveis até:

```text
N
```

Criar testes específicos.

---

# 100. MONTE CARLO

Criar:

```text
MonteCarloEngine
```

Utilizar resultados reais da estratégia/backtest:

```text
trade_returns[]
```

Implementar:

```text
bootstrap
trade sequence randomization
capital paths
drawdown distribution
final equity distribution
percentiles
loss sequence analysis
```

NumPy float64 permitido aqui.

---

# 101. OUT-OF-SAMPLE

Suportar:

```text
TRAIN
VALIDATION
TEST
```

TEST não participa da escolha de parâmetros.

---

# 102. WALK-FORWARD

Criar posteriormente:

```text
WalkForwardEngine
```

Não alterar automaticamente produção.

Resultados servem para análise.

---

# 103. FASES DE IMPLEMENTAÇÃO

## FASE 1 — CORE

Criar:

```text
estrutura
config
logging
Decimal
FastAPI
PostgreSQL
SQLAlchemy
Alembic
```

---

## FASE 2 — EXCHANGE REAL

Criar:

```text
ExchangeAdapter
authentication
server time
account
balances
symbol rules
commissions
best bid/ask
```

Objetivo:

```text
CONECTAR À EXCHANGE REAL
```

sem ainda enviar ordem automaticamente.

---

## FASE 3 — MARKET DATA

Criar:

```text
MarketDataEngine
worker-market-data
historical importer
WebSocket
candles
reconnect
stale detection
```

---

## FASE 4 — FEATURE ENGINE

Criar indicadores e features.

Validar matematicamente.

---

## FASE 5 — STRATEGY

Implementar exatamente:

```text
TrendPullbackV1
```

conforme este documento.

---

## FASE 6 — RISK ENGINE

Implementar:

```text
position sizing
risk limits
symbol filters
balance validation
```

---

## FASE 7 — ORDER INTENT

Implementar:

```text
signals
order_intents
client_order_id
```

---

## FASE 8 — EXECUÇÃO REAL

Implementar:

```text
create order
query order
cancel order
safe retry
idempotency
```

Neste ponto a infraestrutura passa a ser capaz de enviar ordem real quando:

```env
TRADING_MODE=live
```

---

## FASE 9 — FILLS

Implementar:

```text
order lifecycle
partial fills
fees
VWAP
```

---

## FASE 10 — POSITION ENGINE

Implementar:

```text
position
average entry
PnL
```

---

## FASE 11 — PROTEÇÃO

Implementar:

```text
stop
take
break-even
trailing
strategy exit
```

---

## FASE 12 — LEDGER

Implementar ledger imutável.

---

## FASE 13 — RECONCILIAÇÃO

Implementar:

```text
startup reconciliation
periodic reconciliation
```

---

## FASE 14 — EXECUTION WORKER

Criar:

```text
worker-execution
```

para funcionamento contínuo.

---

## FASE 15 — SAFETY

Implementar:

```text
PAUSE
RESUME
EMERGENCY EXIT
risk blocks
state machine
```

---

## FASE 16 — API

Criar endpoints de consulta e controle.

---

## FASE 17 — DASHBOARD

Criar frontend operacional.

---

## FASE 18 — ALERTAS

Implementar AlertService.

---

## FASE 19 — DOCKER

Containers mínimos:

```text
backend-api
worker-execution
worker-market-data
postgres
frontend
reverse-proxy
```

---

## FASE 20 — VPS

Deploy de produção.

Configurar:

```text
Docker
firewall
TLS
environment
database persistence
backups
time sync
logs
restart policies
```

---

## FASE 21 — DATASET

Ativar coleta permanente.

---

## FASE 22 — RESEARCH

Implementar:

```text
BacktestEngine
MonteCarloEngine
Out-of-sample
WalkForwardEngine
```

sem alterar o núcleo live.

---

## FASE 23 — ML

Preparar treinamento utilizando dados acumulados.

ML não substitui Strategy V1 automaticamente.

---

# 104. CRITÉRIO DE MVP LIVE

MVP somente está completo quando consegue:

```text
1. conectar à exchange real

2. consultar saldo

3. carregar regras reais do símbolo

4. receber mercado real

5. detectar candle fechado

6. calcular indicadores

7. executar TrendPullbackV1

8. gerar Signal

9. executar RiskEngine

10. calcular position size

11. criar OrderIntent

12. criar client_order_id

13. enviar ordem

14. acompanhar status

15. processar partial fills

16. construir posição

17. proteger posição

18. executar saída

19. calcular fees

20. calcular PnL

21. registrar ledger

22. reconciliar exchange

23. sobreviver a restart

24. impedir duplicação

25. bloquear operação em estado desconhecido

26. possuir PAUSE

27. possuir EMERGENCY EXIT

28. manter histórico auditável
```

---

# 105. REGRAS PARA A IA DESENVOLVEDORA

A IA deverá:

1. seguir este documento;
2. não inventar APIs;
3. não inventar campos da exchange;
4. consultar documentação oficial atual;
5. não utilizar biblioteca desatualizada sem verificar;
6. não alterar stack sem autorização;
7. não alterar Strategy V1 silenciosamente;
8. não alterar parâmetros silenciosamente;
9. não habilitar live por default;
10. não implementar saque;
11. não enviar ordem sem saldo;
12. não enviar ordem sem RiskEngine;
13. não enviar ordem com dados stale;
14. não confiar apenas no banco;
15. reconciliar com exchange;
16. não utilizar float para ledger;
17. não esconder fees;
18. não esconder slippage;
19. não ignorar partial fill;
20. não considerar timeout como ordem inexistente;
21. não fazer retry cego;
22. utilizar idempotência;
23. não modificar ledger histórico;
24. não usar candle futuro;
25. não usar candle aberto como fechado;
26. não inventar dados ausentes;
27. não permitir modelo ML não versionado;
28. não auto-otimizar produção;
29. criar testes para fórmulas financeiras;
30. preferir bloquear nova operação quando o estado for incerto.

---

# 106. REGRA DE IMPLEMENTAÇÃO POR FASE

Ao iniciar cada fase:

```text
1. ler esta especificação;
2. identificar requisitos da fase;
3. verificar dependências;
4. implementar;
5. criar testes;
6. executar testes;
7. corrigir erros;
8. documentar o que foi criado;
9. somente então avançar.
```

Não pular silenciosamente requisito porque sua implementação é trabalhosa.

Não substituir requisito por TODO.

Se algo não puder ser implementado corretamente:

```text
PARAR
DOCUMENTAR
EXPLICAR O BLOQUEIO
```

---

# 107. NÃO REESCREVER O PROJETO DESNECESSARIAMENTE

Depois que uma fase estiver funcionando:

```text
não substituir componentes estáveis
não reorganizar arquitetura sem necessidade
não mudar contratos internos silenciosamente
```

Alterações estruturais devem preservar migrations e compatibilidade quando possível.

---

# 108. MIGRATIONS

Toda mudança estrutural do PostgreSQL:

```text
ALEMBIC MIGRATION
```

Nunca depender de:

```text
drop database
recreate database
```

como processo normal de atualização.

---

# 109. LOGS

Logs devem possuir contexto:

```text
timestamp
level
service
event
symbol
strategy_version
order_intent_id
client_order_id
exchange_order_id
```

quando aplicável.

Nunca incluir secrets.

---

# 110. BACKUPS

Banco de produção deve possuir rotina de backup.

Backups devem incluir dados necessários para reconstruir:

```text
orders
fills
positions
ledger
strategy versions
config versions
```

---

# 111. CAPITAL REAL

O sistema deve assumir desde o início que está lidando com dinheiro real.

Não criar código do tipo:

```text
"depois melhoramos porque são apenas R$100"
```

Os mesmos mecanismos de:

```text
idempotência
reconciliação
segurança
precisão
auditoria
risco
```

devem existir desde a primeira versão.

---

# 112. EXPECTATIVA DO SISTEMA

O sistema deve conseguir medir objetivamente:

```text
quanto ganhou
quanto perdeu
quanto pagou de fee
quanto perdeu em slippage
qual drawdown
qual win rate
qual average win
qual average loss
qual expectancy
qual profit factor
```

Nunca mascarar resultado negativo.

---

# 113. RECEITA NÃO É GARANTIDA

O objetivo do projeto é criar infraestrutura capaz de executar uma estratégia de trading automaticamente e medir seu desempenho.

O software não deverá assumir que:

```text
TrendPullbackV1 = lucrativa
```

ou que qualquer estratégia produzirá renda mensal constante.

Os resultados reais determinarão isso.

A infraestrutura deverá permitir trocar ou evoluir a estratégia sem reconstruir execução, risco, ledger e exchange.

---

# 114. PRINCÍPIO DE EVOLUÇÃO

Arquitetura:

```text
INFRAESTRUTURA ESTÁVEL
        +
ESTRATÉGIAS VERSIONADAS
        +
DADOS ACUMULADOS
        +
MÉTRICAS
        +
PESQUISA
```

Se TrendPullbackV1 apresentar desempenho inadequado:

```text
NÃO REMENDAR EXECUTION ENGINE
```

Criar:

```text
TrendPullbackV2
```

ou nova estratégia.

Comparar resultados de maneira reproduzível.

---

# 115. APRENDIZADO DO SISTEMA

Desde o primeiro dia:

```text
MARKET DATA
+
STRATEGY DECISIONS
+
ORDERS
+
FILLS
+
FEES
+
SLIPPAGE
+
RESULTADOS
```

devem ser preservados.

Isso criará base própria para:

```text
análise
backtesting
otimização
machine learning
novas estratégias
```

---

# 116. PRINCÍPIO DE SEGURANÇA

Sempre que houver dúvida:

```text
UNKNOWN
↓
BLOCK NEW ENTRY
↓
QUERY EXCHANGE
↓
RECONCILE
↓
VALIDATE
↓
RESUME
```

Nunca:

```text
UNKNOWN
↓
ASSUME
↓
TRADE
```

---

# 117. PRINCÍPIO DE EXECUÇÃO

A prioridade do sistema será:

```text
1. NÃO DUPLICAR ORDENS

2. NÃO PERDER CONTROLE DA POSIÇÃO

3. NÃO OPERAR COM ESTADO DESCONHECIDO

4. PROTEGER POSIÇÃO EXISTENTE

5. RESPEITAR RISCO

6. REGISTRAR TODA MOVIMENTAÇÃO

7. EXECUTAR A ESTRATÉGIA

8. MEDIR RESULTADOS

9. COLETAR DADOS

10. EVOLUIR A ESTRATÉGIA
```

---

# 118. REGRA FINAL

Este projeto é um sistema de produção.

O agente desenvolvedor deverá trabalhar assumindo que uma falha poderá causar perda financeira real.

Portanto:

```text
NÃO INVENTAR

NÃO ADIVINHAR

NÃO IGNORAR ERRO

NÃO DUPLICAR ORDEM

NÃO IGNORAR PARTIAL FILL

NÃO IGNORAR FEE

NÃO IGNORAR SLIPPAGE

NÃO IGNORAR RECONCILIAÇÃO

NÃO OPERAR COM DADOS STALE

NÃO ALTERAR ESTRATÉGIA SILENCIOSAMENTE

NÃO ALTERAR RISCO SILENCIOSAMENTE

NÃO EXPOR CREDENCIAIS

NÃO IMPLEMENTAR SAQUE
```

Quando o sistema possuir informação confiável:

```text
CALCULAR
↓
VALIDAR
↓
EXECUTAR
↓
CONFIRMAR
↓
REGISTRAR
↓
RECONCILIAR
```

Quando não possuir:

```text
NO TRADE
```

# FIM DA ESPECIFICAÇÃO