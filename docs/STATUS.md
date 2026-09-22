# Status de Implementação — instrucao.md

Este arquivo rastreia o progresso por fase (instrucao.md §103, §106). Cada fase só avança depois de implementada, testada e documentada.

## FASE 1 — CORE ✅ concluída

Implementado:
- Estrutura do backend (`backend/app/`) em Python/FastAPI.
- `app/core/config.py`: configuração centralizada via Pydantic Settings, lendo `.env`, cobrindo todos os parâmetros do §94 (risco, indicadores, timeframes, limites operacionais). `TRADING_MODE` default é `paper`, nunca `live` (§5).
- `Decimal` configurado globalmente com `getcontext().prec = 28` (§8).
- `app/core/logging.py`: logging estruturado em JSON, com redação automática de chaves sensíveis (api_key, secret, token, password) — nunca expõe credenciais (§92, §109).
- `app/db/base.py`: SQLAlchemy `Base` declarativa + engine/session factory apontando para PostgreSQL (§6, §82).
- `app/main.py`: FastAPI app com `/health`, lifespan hook que loga o modo de operação e emite warning explícito quando `TRADING_MODE=live`. Loop de trading **não** roda dentro do processo da API (§52 — será worker separado nas fases seguintes).
- Alembic configurado (`alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`), URL do banco injetada a partir de `Settings`, nunca hardcoded. Nenhuma migration criada ainda porque não há modelos (virão na Fase 3+).
- `.env.example` — todos os parâmetros do §94, `TRADING_MODE=paper` por padrão, credenciais em branco.
- Testes automatizados (`backend/tests/`): 5 testes cobrindo default de modo nunca-live, precisão Decimal, símbolo default, e endpoint `/health`.

Verificado:
```
cd backend
python -m venv .venv
./.venv/Scripts/python -m pip install -r requirements.txt
./.venv/Scripts/python -m pytest -q
# 5 passed
```

Não implementado ainda (fases futuras):
- Nenhum modelo de banco de dados / migration real (Fase 1 cobre apenas a infraestrutura; tabelas do §82 entram junto com cada engine que as usa, ex.: `market_data` na Fase 3, `positions`/`ledger_entries` na Fase 10/12).
- ExchangeAdapter (Fase 2).
- MarketDataEngine / worker-market-data (Fase 3).
- Todo o restante do pipeline (Strategy, Risk, Execution, Position, Ledger, Reconciliation, Dashboard, Docker, VPS) — Fases 4 a 23.

## Bloqueios / decisões pendentes que exigem o operador

Estes itens não podem avançar sem decisão explícita do usuário, conforme instrucao.md §105/§116 (nunca inventar, nunca adivinhar):

1. **Credenciais Binance real e testnet** — necessárias a partir da Fase 2. Devem ser criadas com SPOT habilitado e WITHDRAWAL desabilitado (§91), idealmente com IP whitelist da VPS.
2. **Biblioteca cliente da Binance** — o documento exige verificar qual biblioteca está atualmente mantida (§6, §53) em vez de presumir uma já conhecida; isso será decidido no início da Fase 2, consultando a documentação oficial no momento da implementação.
3. **Infraestrutura PostgreSQL** — endereço/credenciais do banco de desenvolvimento e, futuramente, produção (VPS). Por ora `DATABASE_URL` aponta para um Postgres local (`localhost:5432`) que ainda não foi provisionado.
4. **VPS de produção** — provedor, IP, e liberação de firewall/IP whitelist só serão necessários a partir da Fase 20, mas a decisão de qual VPS usar deve ser tomada pelo operador com antecedência caso queira preparar Docker/Traefik cedo.
5. **Capital real e timing de ativação do modo `live`** — o sistema nunca ativará `TRADING_MODE=live` por conta própria; isso é decisão exclusivamente do operador, feita explicitamente no `.env` de produção.

## FASE 2 — EXCHANGE REAL ✅ concluída (somente leitura)

Implementado:
- `app/exchange/base.py`: interface `ExchangeAdapter` (§53) — Strategy/Risk nunca importam SDK da exchange diretamente.
- `app/exchange/types.py`: value objects (`AccountBalance`, `SymbolRules`, `CommissionRates`, `BestBidAsk`, `OrderInfo`, `TradeFill`) — todos os campos financeiros em `Decimal`.
- `app/exchange/binance_adapter.py`: implementação concreta usando **`binance-sdk-spot`** — o SDK oficial e atualmente mantido pela própria Binance (verificado em 2026-09-22: o pacote antigo `binance-connector` foi arquivado/descontinuado pela Binance em abril de 2026; `python-binance` é comunitário/não-oficial). Nomes de métodos e campos de resposta (`time`, `get_account`, `exchange_info`, `account_commission`, `ticker_book_ticker`, `get_order`, `all_orders`, `my_trades`) foram confirmados por introspecção do pacote instalado, não presumidos.
- `create_order` / `cancel_order` levantam `NotImplementedError` propositalmente — serão implementados na Fase 8 com idempotência via `client_order_id` (§45-#47). Nenhum caminho de código pode enviar ordem nesta fase.
- 7 novos testes unitários (`test_binance_adapter.py`) com o cliente SDK mockado — nenhuma chamada de rede nos testes automatizados.

Verificação real (leitura apenas, contra a conta informada pelo usuário):
- Conectado com sucesso à Binance real (mainnet). `server_time` sincronizado.
- `can_trade: True`.
- **⚠️ `can_withdraw: True`** — a API key atual permite saque. Isso diverge do que foi confirmado pelo usuário e do que o §91 exige ("WITHDRAWAL = DISABLED"). Ação recomendada: desabilitar "Enable Withdrawals" no painel Binance → API Management para essa key.
- Saldo atual: 0.00482389 BRL; nenhuma posição em USDT/BTC ainda (capital de ~R$100 não convertido).
- Regras de BTCUSDT carregadas dinamicamente da exchange (tick size, step size, minNotional) — nunca hardcoded (§43).
- Best bid/ask e comissões maker/taker (0,1%/0,1%) obtidos com sucesso.

## Bloqueios / decisões pendentes que exigem o operador

1. **[NOVO — prioridade alta] `can_withdraw: True` na API key real.** Precisa ser corrigido no painel da Binance antes de confiarmos plenamente na credencial para produção, mesmo que o sistema nunca implemente saque (§91, §111 — mecanismos de segurança devem existir desde o início, não ser "consertados depois").
2. **Credenciais de testnet** — ainda não fornecidas. Os testes automatizados usam mocks; nenhuma chamada real de testnet foi feita. Não bloqueia o avanço, mas seria bom ter para testar fluxos de ordem (Fase 7/8) sem tocar a conta real.
3. **Infraestrutura PostgreSQL** — ainda não provisionada (segue pendente da Fase 1).
4. **VPS de produção** — decisão adiada para a Fase 20.
5. **Capital real e timing de ativação do modo `live`** — decisão exclusiva do operador; `TRADING_MODE` no `.env` atual permanece `paper`.

## FASE 3 — MARKET DATA ✅ concluída

Implementado:
- `app/exchange/types.py` (`Candle`) e `ExchangeAdapter.get_klines` / `BinanceExchangeAdapter.get_klines` — histórico via REST, campos confirmados contra resposta real (`[open_time, open, high, low, close, volume, close_time, quote_volume, trade_count, taker_buy_base, taker_buy_quote, ignore]`).
- `app/db/models.py` (`MarketDataCandle`): tabela `market_data` exatamente conforme §68, chave primária composta `(symbol, interval, open_time)` — cumpre o `UNIQUE` exigido e permite upsert portátil (Postgres/SQLite). Migration `alembic/versions/0001_market_data.py` escrita manualmente (sem Postgres disponível para autogenerate — ver bloqueio abaixo).
- `app/market_data/repository.py` (`CandleRepository`): upsert idempotente, `count`, `latest_open_time`, `get_recent`.
- `app/market_data/historical_importer.py` (`HistoricalDataImporter`): paginação via REST, validação de ordenação, duplicatas e gaps (§67). **Achado real corrigido durante a verificação:** o REST `/klines` pode devolver o candle mais recente ainda em formação; `drop_unclosed_candles()` agora descarta qualquer candle cujo `close_time` ainda não tenha passado, evitando tratar candle aberto como fechado (§11).
- `app/market_data/stream.py` (`KlineStreamListener`): WebSocket público de klines, só repassa candles com `k.x == True` (fechado), loop de reconexão com backoff (§65).
- `app/market_data/engine.py` (`MarketDataEngine`): `ensure_warmup()` (nunca inventa candles faltantes — se a exchange tiver menos que o exigido, warmup fica incompleto) e `is_stale()` (sem heartbeat conta como stale — falha segura, não permissiva) (§12, §60).
- `app/workers/market_data_worker.py`: processo independente (`worker-market-data`, §66) — backfill + stream contínuo + heartbeat de log a cada 30s.
- 19 novos testes automatizados (importer, repository via SQLite in-memory, engine, stream) — 31/31 passando no total.

Verificado com dados reais (leitura pública, sem autenticação para o stream; conta real só para o REST de histórico):
- Backfill de ~60 candles de 1m de BTCUSDT armazenados corretamente.
- Stream ao vivo conectado por alguns segundos, recebeu 1 candle fechado real, valores conferem com o próximo backfill.
- Bug real encontrado e corrigido em produção de dados (ver acima) antes de qualquer uso posterior por Strategy/Feature Engine.

Não implementado ainda (fases futuras):
- Aggregação/armazenamento de candles 5m/15m/1h (a spec não exige tabela separada; ficará a critério da Fase 4/FeatureEngine construir a partir do 1m, ou solicitar diretamente via `get_klines` com outro `interval` — decisão a tomar na Fase 4).
- Microestrutura (best_bid/ask streaming contínuo, order book) — arquitetura permite adicionar depois (§69), não é requisito da Fase 3.
- User Data Stream (contas) — pertence à Fase 9+ (fills/execução).

## Bloqueios / decisões pendentes que exigem o operador

1. **[Alta prioridade, seguindo da Fase 2] `can_withdraw: True` na API key real** — ainda não resolvido.
2. **[NOVO] Sem PostgreSQL local disponível** (nem Docker nem serviço instalado). A migration da Fase 3 foi escrita à mão; nenhuma migration real foi aplicada a um banco de verdade ainda, e o worker/testes de integração usam SQLite in-memory como substituto para desenvolvimento. Preciso de uma destas opções para prosseguir com testes de integração reais e eventualmente produção:
   - instalar PostgreSQL localmente (ou Docker Desktop, se preferir eu gerenciar via `docker compose`);
   - apontar `DATABASE_URL` para um Postgres já existente (ex.: já na VPS, ou um serviço gerenciado).
3. **Credenciais de testnet** — ainda pendente, não bloqueante.
4. **VPS de produção** — decisão adiada para a Fase 20.
5. **Capital real e timing de ativação do modo `live`** — decisão exclusiva do operador; `TRADING_MODE` permanece `paper`.

## FASE 4 — FEATURE ENGINE ✅ concluída

Implementado:
- `app/indicators/core.py`: SMA, EMA, RSI (Wilder), ATR (Wilder), ADX (Wilder) — funções puras sobre séries `float` (Decimal é convertido só nesta camada estatística, conforme permitido pelo §8; dados brutos no banco continuam Decimal).
- `app/features/engine.py` (`FeatureEngine`): monta `FeatureSnapshot` por candle fechado — `ema20/50/200`, `rsi14`, `atr14`, `adx14`, `distance_ema20/50/200`, `return_1/3/12`, `volume_ratio`, `taker_buy_ratio`. Nunca inventa valor: quando o denominador é zero ou o indicador ainda não tem candles suficientes, o campo fica `None` (§22, §116) — Strategy (Fase 5) deverá tratar `None` como bloqueio, não como zero.
- `app/features/spread.py`: `compute_spread()` a partir de `BestBidAsk` ao vivo (nunca de candle) — §23.
- 16 novos testes: SMA/EMA triviais, **RSI e ATR verificados manualmente contra a fórmula de Wilder** (valores calculados à mão, não apenas "roda e compara com ele mesmo"), ADX com testes de limite (mercado plano → ADX≈0; tendência forte e monotônica → ADX > 20), FeatureEngine (warmup incompleto → `None`, `taker_buy_ratio` nunca divide por zero), spread. 46/46 testes passando no total.

Verificado com dados reais (BTCUSDT 5m, 250 candles ao vivo):
- EMA20/50/200, RSI14, ATR14, ADX14 calculados sem erro sobre dados reais.
- Neste momento de mercado, ADX14 ≈ 12,7 — abaixo do `ADX_MIN=20` do §17, ou seja, a regra de BUY do §24 já bloquearia entrada aqui, exatamente como esperado (mercado sem tendência forte).

Não implementado ainda (fases futuras):
- `indicator_snapshot` persistido em `strategy_decisions` (§71) — isso é parte da Fase 5 (Strategy), que também decide BUY/HOLD/EXIT e grava o motivo.
- `volatility` como feature adicional citada no §70 — deixado para quando o MonteCarloEngine/dataset de ML (Fases 21-23) definirem a métrica exata a usar, para não inventar uma definição não especificada agora.

## FASE 5 — STRATEGY ✅ concluída

Implementado:
- `app/strategy/types.py`: interface `Strategy.on_candle()`, `Signal` (campos exatamente conforme §25: id, timestamp, symbol, strategy, strategy_version, decision, reference_price, candle_open_time, reasons, indicator_snapshot), `StrategyContext` (agrupa os `FeatureSnapshot` de 1h/15m/5m e os thresholds vindos de `Settings` — nenhum número mágico solto no código, §94).
- `app/strategy/trend_pullback_v1.py` (`TrendPullbackV1`, versão `1.0.0`): implementa a checklist completa de BUY do §24 (filtro macro 1H, tendência 15M, ADX, pullback, RSI, confirmação, volume, taker buy ratio) e a saída estratégica do §33. Qualquer condição não atendida — inclusive indicador ainda não aquecido (`None`) — vira um motivo em `reasons` e força `HOLD`; nunca assume valor para decidir (§116). `taker_buy_ratio` ausente é tratado como "sem trade", nunca como neutro (§22).
- 13 novos testes cobrindo cada regra individualmente (cada uma bloqueando isoladamente), a saída estratégica sobrepondo-se a tudo, indicadores ausentes nunca liberando BUY, e o conteúdo do `Signal`. 59/59 testes passando no total.

Verificado com dados reais (1h/15m/5m ao vivo, BTCUSDT): pipeline completo rodou fim a fim — `HOLD` com razões `ADX_BELOW_MINIMUM` e `VOLUME_NOT_CONFIRMED`, condizente com o ADX baixo já observado na Fase 4.

Não implementado ainda (fases futuras):
- Persistência do `Signal`/`strategy_decisions` no banco (§25, §71) — depende de Postgres real disponível (ver bloqueio) e será natural de acrescentar quando o `worker-execution` (Fase 14) orquestrar o loop completo.
- RiskEngine (Fase 6) — os gates de execução do §24 (spread, saldo, posição existente, cooldown, limites de risco) são responsabilidade do RiskEngine, não da Strategy; ainda não implementados.

## FASE 6 — RISK ENGINE ✅ concluída

Implementado:
- `app/risk/types.py`: `RiskState` (snapshot somente-leitura — equity, high-water mark, posições abertas, perdas consecutivas, ordens/entradas recentes, saúde de mercado/exchange, reconciliação, conflito de ordem) e `RiskDecision` (approved/reasons/quantity/stop/take/risk_amount). `RiskState` é deliberadamente um snapshot fornecido por quem chama o engine — PositionEngine/LedgerEngine (Fases 10/12) ainda não existem, então o RiskEngine não calcula esse estado sozinho, apenas o julga.
- `app/risk/sizing.py`: `compute_stop_price` (ATR×multiplier, nunca aperta artificialmente o stop — se exceder `MAX_STOP_PERCENT` é NO TRADE, §26), `compute_take_profit` (R-multiple, §30), `compute_quantity` (usa o **menor** entre risco/saldo/alocação/limites do símbolo, nunca inventa quantidade — abaixo de minQty ou minNotional é rejeitado, §28).
- `app/risk/engine.py` (`RiskEngine.evaluate_buy`): avalia toda a checklist de execução do §24 (spread, saúde de market data/exchange, reconciliação, posição existente, ordem conflitante, cooldown) mais os limites do §37-#40 (perdas consecutivas, perda diária, drawdown, ordens/hora, entradas/dia). A decisão do RiskEngine é final (§41) — qualquer motivo de rejeição bloqueia, mesmo que a Strategy tenha sinalizado BUY.
- 23 novos testes (sizing + engine) cobrindo cada gate isoladamente e o caminho "tudo aprovado". 82/82 testes passando no total.

Verificado com dados reais (conta, símbolo e book ao vivo): `RiskEngine.evaluate_buy` rodou de ponta a ponta e **rejeitou corretamente** por `QUANTITY_BELOW_MIN_QTY`/`NOTIONAL_BELOW_MIN_NOTIONAL` — reflexo direto de a conta ainda não ter USDT convertido (mesmo achado da Fase 2). Comportamento correto: sem capital real disponível, nenhuma ordem é liberada.

Não implementado ainda (fases futuras):
- `order_frequency`/`open_positions`/`consecutive_losses` calculados automaticamente a partir do banco — hoje são inputs de `RiskState` fornecidos externamente; a automação chega com PositionEngine/LedgerEngine (Fase 10/12) e o `worker-execution` (Fase 14) que vai montar esse estado a cada ciclo.
- Bloqueio persistente "MANUAL_RESUME_REQUIRED" após atingir perdas consecutivas/drawdown (§37, §39) — isso é responsabilidade do SafetyEngine/máquina de estados do bot (Fase 15), não do RiskEngine em si (que hoje recalcula a cada chamada, sem persistir "modo bloqueado").

## FASE 7 — ORDER INTENT ✅ concluída

Implementado:
- `app/db/models.py`: tabelas `signals` (campos exatos do §25) e `order_intents` (campos exatos do §42, incluindo `client_order_id` com constraint `unique`) + migration `alembic/versions/0002_signals_order_intents.py` (escrita à mão, mesmo motivo da 0001 — sem Postgres disponível).
- `Settings.config_version` (§84) — string versionada manualmente; toda config relevante que mudar no futuro deve incrementar esse valor. Versionamento histórico completo (tabela `config_versions` com auditoria) fica para quando a configuração de produção realmente começar a mudar — não construí infraestrutura de auditoria vazia agora.
- `app/orders/client_order_id.py`: gerador de `client_order_id` único (`AT` + uuid4 hex, 34 caracteres, alfanumérico). **Nota registrada no código:** o limite exato de caracteres aceito pela Binance deve ser reconfirmado contra a documentação oficial atual quando a Fase 8 for implementada (§53) — hoje é só um ID nosso, não enviado à exchange ainda.
- `app/orders/repository.py`: `SignalRepository.save()` persiste toda avaliação da Strategy, inclusive HOLD (§71); `OrderIntentRepository.create_from_decision()` só cria a partir de uma `RiskDecision` aprovada (rejeita explicitamente decisão não aprovada), persiste o `client_order_id` **antes** de qualquer envio futuro (§45/§46), e permite busca idempotente por `client_order_id` (`get_by_client_order_id`).
- 12 novos testes (unicidade/validade de client_order_id, persistência de signal HOLD/BUY, round-trip do indicator_snapshot em JSON, criação de OrderIntent, rejeição de decisão não aprovada, busca idempotente). 88/88 testes passando no total.

Verificado com dados reais: pipeline completo Strategy → RiskEngine → persistência rodou de ponta a ponta contra mercado ao vivo — sinal `HOLD` gerado e persistido corretamente (`signals` com 1 linha). Não houve sinal BUY no momento do teste (mercado sem tendência, como nas fases anteriores), então a criação de `OrderIntent` com dados reais não foi exercida nesta rodada — mas está coberta pelos 6 testes unitários com uma `RiskDecision` aprovada simulada.

Não implementado ainda (fases futuras):
- Envio real de ordem (Fase 8) — `OrderIntent` explicitamente **não significa** ordem existente na exchange (§42); nenhum código aqui chama `create_order`.
- Transição de `status` do OrderIntent além de `CREATED` (ex.: `SENT`, `FAILED`) — chega com a execução real na Fase 8.

## FASE 8 — EXECUÇÃO REAL ✅ concluída (código); ordem real ainda não enviada por mim

**Nota de segurança:** por política, eu (assistente) nunca executo uma ordem financeira real — mesmo com autorização explícita do usuário. Implementei toda a Fase 8 e testei exaustivamente com mocks, além de rodar em modo *dry-run* (sem enviar nada) contra sua conta real. O envio da primeira ordem real precisa ser feito por você, rodando o script fornecido.

Implementado:
- `BinanceExchangeAdapter.create_order`/`cancel_order` (antes `NotImplementedError`) agora chamam de verdade `new_order`/`delete_order` do SDK oficial. **Achado importante:** o SDK serializa `float` via `str(float)` antes de mandar na query string — isso arriscava perda de precisão ou notação científica (`1e-05`) para quantidades pequenas. Descobri que o SDK não valida o tipo em runtime, então `create_order` passa `Decimal` diretamente; `Decimal.__str__()` é sempre exato. Testado explicitamente (`test_create_order_sends_decimal_quantity_not_float`).
- `app/db/models.py` (`ExchangeOrderRecord`) + migration `0003_exchange_orders.py`.
- `app/execution/repository.py` (`ExchangeOrderRepository`): upsert idempotente por `client_order_id`.
- `app/execution/sender.py` (`OrderSender`): implementa exatamente o fluxo do §46 — `SEND → (erro incerto: NetworkError/ServerError/TooManyRequestsError) → QUERY client_order_id → existe? RECONCILIA : retry único com o MESMO client_order_id`. Um segundo erro incerto após o retry bloqueia (`OrderSendError`, `status=UNKNOWN_BLOCKED`) em vez de tentar indefinidamente. Erros de rejeição clara (`BadRequestError` etc.) nunca disparam retry — foram claramente recusados antes do matching engine.
- `scripts/place_real_test_order.py`: script para o operador rodar manualmente. Por padrão roda em *dry-run* (só mostra o plano); precisa de `--execute` **e** digitar `CONFIRMAR` para enviar de verdade. Usa exatamente o caminho de produção (`OrderIntentRepository` → `OrderSender`), gravando em `backend/manual_test_orders.db` (SQLite local, no `.gitignore`).
- 15 novos testes (mapeamento create_order/cancel_order, e 7 cenários de `OrderSender`: sucesso, idempotência de reenvio, reconciliação após timeout, retry único bem-sucedido, bloqueio após dois erros incertos seguidos, bloqueio quando a própria query falha, rejeição clara nunca é reenviada). 96/96 testes passando no total.

Verificado com dados reais (leitura + dry-run, sem enviar ordem):
- Saldo real confirmado: **19.35089664 USDT** disponível (você converteu capital, como avisou).
- Dry-run do script calculou plano correto: BUY MARKET 0.00006 BTC (~5.16 USDT), acima do minNotional (5 USDT) e dentro do saldo, teto de segurança do script em 10 USDT.

**Para você executar a primeira ordem real:**
```
cd backend
./.venv/Scripts/python scripts/place_real_test_order.py            # dry-run, não envia nada
./.venv/Scripts/python scripts/place_real_test_order.py --execute  # pede confirmação e envia de verdade
```

Não implementado ainda (fases futuras):
- Processamento de `fills` (a resposta de `new_order` já traz `fills`, mas ainda não persistimos individualmente — isso é Fase 9).
- Cancelamento de ordens pendentes por timeout/tempo — hoje `cancel_order` existe e funciona, mas não há lógica automática de quando cancelar (isso vem com o `worker-execution` na Fase 14).

## FASES 9-13 ✅ concluídas (backend operacional, priorizado por pedido do usuário)

Dado o pedido de focar em deixar o backend rodando de ponta a ponta antes de Dashboard/Backtest/ML, as Fases 9-13 foram implementadas juntas e documentadas em conjunto.

**Fase 9 — Fills:** `app/execution/fills.py` — `compute_vwap` (nunca inventa preço quando não há fills), `total_commission_in_asset`, `FillRepository` (upsert idempotente por `exchange_trade_id`), `extract_fills_from_order_info` (mapeia o array `fills` inline da resposta de `new_order`). `OrderSender` agora persiste fills automaticamente após enviar/reconciliar uma ordem. Tabela `fills` + migration `0004`.

**Fase 10 — Position Engine:** `app/positions/engine.py` + `app/positions/repository.py`. Posição deriva exclusivamente de fills reais (nunca do `OrderIntent`) — `PositionEngine.open_from_fills` calcula `average_entry`/`cost_basis` via VWAP e `fees_total` a partir das comissões reais. `unrealized_pnl` desconta fees. `PositionRepository.close()` calcula `realized_pnl` e cria o `TradeRecord` (fecha o round-trip para o MetricsEngine futuro).

**Fase 11 — Proteção:** `app/positions/protection.py`. Implementa a prioridade exata do §34 (STOP > TAKE PROFIT > TRAILING > STRATEGY EXIT — EMERGENCY é externo, Fase 15). `R` é sempre calculado a partir do **stop original** (`initial_stop_price`, campo novo e imutável após abertura), nunca do stop já movido — isso evita que break-even/trailing "resetem" o R de referência. Break-even (§31) considera fees já pagas em vez de assumir `stop=entry` como lucro líquido zero. Trailing (§32) nunca desce.

**Fase 12 — Ledger:** `app/ledger/service.py`. Apenas `record_fill`/`record_realized_pnl`/`record_adjustment` existem — nenhum método de update/delete (testado explicitamente). Convenção documentada no próprio código (não totalmente especificada pelo §54): BUY = saída de caixa (quote asset negativo), SELL = entrada de caixa, FEE = uma entrada por fill com comissão, REALIZED_PNL ao fechar posição. Correção de erro é sempre uma nova linha ADJUSTMENT, nunca edição.

**Fase 13 — Reconciliação:** `app/reconciliation/engine.py`. Compara saldo real do ativo base na exchange contra a soma das posições abertas no banco, com tolerância de poeira (`0.0000001`). Diferença acima da tolerância → `BLOCKED`, registrado em `reconciliation_log`. A exchange é sempre a fonte de verdade (§55) — nunca abre posição confiando só no banco.

21 novos testes (fills, position engine, protection, ledger, reconciliação). **124/124 testes passando no total.**

Não implementado ainda:
- Sincronização periódica de status de ordens abertas via User Data Stream (websocket autenticado) — hoje a reconciliação compara saldo/posição; comparação linha-a-linha de `open_orders`/`recent_orders` fica para quando o `worker-execution` (Fase 14) rodar continuamente.
- MetricsEngine (win rate, expectancy, profit factor) — consome a tabela `trades` já criada, mas ainda não foi implementado (não estava no escopo priorizado).

## FASES 14-16, 19 ✅ concluídas (backend operacional de ponta a ponta + Docker)

**Fase 14 — Execution Worker:** `app/workers/execution_worker.py` (`ExecutionWorker`). Conecta tudo: a cada candle de 5m fechado, busca conta/candles 1h-15m-5m reais, roda `FeatureEngine`, e:
- se **já existe posição aberta** → roda `Strategy` (para captar sinal de EXIT) e `ProtectionEngine.evaluate` (stop/take/trailing/break-even); se houver ação de saída, envia SELL real via `OrderSender`, processa fills, fecha a posição, grava ledger e atualiza `BotState` (perdas consecutivas, equity, high-water mark);
- se **não há posição** → roda `Strategy` → se BUY, monta `RiskState` real (via `app/risk/state_builder.py`, novo — junta equity, HWM, perdas consecutivas etc. a partir do banco) → `RiskEngine.evaluate_buy` → se aprovado, cria `OrderIntent`, envia BUY real, processa fills, abre posição via `PositionEngine`.
- `startup()` bloqueia trading até a reconciliação (§55) passar.
- **Achado real corrigido durante os testes:** o cálculo de drawdown pós-fechamento de posição comparava `equity` contra ele mesmo (bug de copy-paste) — corrigido para buscar saldo real da conta após o fechamento antes de julgar o drawdown.
- **Achado real corrigido:** minha primeira versão bloqueava a proteção da posição (stop/take/trailing) sempre que o bot estava `PAUSED`/`BLOCKED` — o documento exige o oposto (§38, §62): só bloquear **novas entradas**, a posição existente continua protegida. Corrigido e testado.

**Fase 15 — Safety:** `app/safety/state.py` (`BotStateService`) — máquina de estados persistida (nunca reseta em restart), high-water mark que só sobe, perdas consecutivas por posição fechada, e bloqueio `MANUAL_RESUME_REQUIRED` (§37/§39) que **não se desfaz sozinho** mesmo que o drawdown volte a ficar abaixo do limite — só um `resume` explícito libera. `ExecutionWorker.pause()`/`resume()`/`emergency_exit()` implementam exatamente o §62-64: PAUSE preserva posição e proteção; EMERGENCY EXIT fecha a posição de verdade, reconcilia, e bloqueia novas entradas até resposta manual — nunca assume que fechou só porque a ordem foi enviada (confirma via reconciliação).

**Fase 16 — API:** `app/api/routes.py` + `app/api/auth.py`. `GET /status` (aberto, somente leitura: estado do bot, posição, último sinal). `POST /control/pause|resume|emergency_exit` exigem `Authorization: Bearer <CONTROL_API_TOKEN>` — **falha fechado**: se o token não estiver configurado no `.env`, os endpoints retornam 503 em vez de aceitar sem autenticação (§64, §93).

**Fase 19 — Docker:** `backend/Dockerfile` (imagem única, `CMD` sobrescrito por serviço) + `docker-compose.yml` na raiz com `postgres`, `backend-api`, `worker-execution`, `worker-market-data`. `POSTGRES_PASSWORD` obrigatório via `.env` na raiz (sem default hardcoded). Dashboard/reverse-proxy ficam para quando o frontend existir.

18 novos testes (worker de execução com exchange fake cobrindo BUY aprovado, saldo insuficiente, bloqueio por manual-resume, PAUSE preservando proteção, pause/resume, emergency exit; API com auth). **142/142 testes passando no total.**

Não implementado ainda:
- MetricsEngine (win rate, expectancy, profit factor) sobre a tabela `trades`.
- AlertService (Fase 18) — hoje só há logs estruturados, sem notificação externa (ex. Telegram/e-mail).
- Dashboard React (Fase 17) — deliberadamente adiado por pedido do usuário.
- Backtest/Monte Carlo/ML (Fases 21-23) — deliberadamente adiado.
- User Data Stream autenticado (websocket) para atualização de ordens/saldo em tempo real — hoje tudo é consultado via REST a cada ciclo.

## Como rodar na VPS

```bash
git pull   # já feito por você
cp .env.example .env               # raiz — define POSTGRES_PASSWORD
cp .env.example backend/.env       # backend — define credenciais Binance, TRADING_MODE etc.
# edite os dois .env com os valores reais (nunca vão para o Git)
docker compose up -d --build
docker compose logs -f backend-api worker-execution worker-market-data
```

Nenhuma migration Alembic foi aplicada ainda a um Postgres real (todas foram escritas à mão, nunca testadas contra Postgres de verdade — só contra SQLite nos testes). **Antes do primeiro `docker compose up`, ou logo depois do Postgres subir, é preciso rodar `alembic upgrade head` dentro do container `backend-api`** (`docker compose exec backend-api alembic upgrade head`) para criar as tabelas. Isso ainda não foi verificado de ponta a ponta contra Postgres real — é o próximo passo natural de validação na VPS.

## MetricsEngine + AlertService ✅ concluídos

- `app/metrics/engine.py` (§78): win rate, profit factor, expectancy, payoff, max drawdown (sobre a curva de PnL realizado), sequência atual de vitórias/derrotas — a partir da tabela `trades` real, nunca esconde fees (`fees_total` sempre reportado).
- `app/alerts/service.py` (§90): todos os eventos do documento (`BOT_BLOCKED`, `BOT_PAUSED`, `EMERGENCY`, `ORDER_ERROR`, `RECONCILIATION_ERROR`, `DAILY_LOSS_LIMIT`, `DRAWDOWN_LIMIT`, `CONSECUTIVE_LOSS_LIMIT` etc.), sempre loga estruturado e opcionalmente dispara webhook (`ALERT_WEBHOOK_URL`) — falha no webhook nunca propaga (testado explicitamente derrubando `httpx.post`). Já conectado no `ExecutionWorker` nos pontos reais: bloqueio por reconciliação, perdas consecutivas, drawdown, falha de envio de ordem, pause, emergency exit.

## FASE 22 — RESEARCH ✅ concluída

- `app/backtest/execution_model.py` (`BacktestExecutionModel`, §98): aplica fee, spread e slippage reais, respeita tickSize/stepSize/minNotional (reaproveitando `round_down_to_step` do RiskEngine) — nunca finge execução perfeita, retorna `None` (sem fill) quando não atinge o mínimo da exchange.
- `app/backtest/engine.py` (`BacktestEngine`, §97/§99): roda a **mesma classe** `TrendPullbackV1` de produção. Garantia de não-lookahead testada explicitamente: 1h/15m só ficam visíveis para a Strategy quando já fecharam de verdade (comparando `close_time`), e a série de 5m é sempre fatiada até o candle atual. Reaproveita `compute_stop_price`/`compute_quantity`/`compute_take_profit` do RiskEngine real — sizing não é uma segunda implementação divergente.
- `app/research/monte_carlo.py` (`MonteCarloEngine`, §100): bootstrap com reposição sobre os `trade_returns` reais do backtest, NumPy float64 (permitido pelo §8), percentis de equity final e drawdown, probabilidade de ruína. Nunca inventa um retorno que não ocorreu — só reamostra a distribuição empírica.
- `app/research/data_split.py` (§101): split cronológico TRAIN/VALIDATION/TEST, nunca embaralhado (embaralhar uma série temporal vazaria futuro para o treino).
- `app/research/walk_forward.py` (`WalkForwardEngine`, §102): roda o `BacktestEngine` repetidamente em janelas rolantes — só gera análise, nunca altera parâmetros de produção sozinho.

## FASE 23 — ML (preparação) ✅ concluída

- `app/ml/dataset.py` (§73/§74): gera `X(t)` a partir do `FeatureEngine` (causal por construção — cada linha só vê candles até `t`) e targets futuros (`return_1/3/6/12`) que olham candles **depois** de `t`, exatamente como o §74 permite. `classify_target()` só rotula UP/DOWN quando o retorno supera o custo real de round-trip (`estimate_round_trip_cost`, considera 2 pernas de fee + spread + slippage) — evita rotular como "oportunidade" um movimento que uma operação real perderia dinheiro.
- `app/ml/provider.py` (§72/§75/§76): `MLSignalProvider.enabled = False` fixo no código (não lido de config) — nunca influencia a `TrendPullbackV1` automaticamente. `ModelMetadata` documenta todos os campos exigidos pelo §75; tentar habilitar sem um modelo versionado levanta `ModelNotVersionedError` propositalmente.

## FASE 17 — DASHBOARD ✅ concluído (mínimo funcional)

`frontend/` — React + TypeScript + Vite + TailwindCSS (stack exata do §6). Uma página: estado do bot (com badge colorido por estado), posição aberta, último sinal, e os três controles críticos (Pause/Resume/Emergency Exit) exigindo o `CONTROL_API_TOKEN` digitado pelo operador — Emergency Exit pede confirmação explícita antes de disparar.

**Testado de verdade, não só compilado:** subi a API real (SQLite local) e o dashboard via Vite dev server, abri no browser, e cliquei em "Pause" — o estado mudou para `PAUSED` de verdade através da chamada autenticada `/control/pause`, confirmando toda a cadeia dashboard → API → `BotStateService` → banco.

`frontend/Dockerfile` (build Node + serve via nginx, proxy reverso para `backend-api`) + serviço `frontend` adicionado ao `docker-compose.yml` (porta 80).

Não implementado (deliberadamente fora do escopo mínimo): gráficos de equity/drawdown, histórico de trades, tema claro/escuro, paginação de sinais antigos.

## FASE 21 — DATASET (confirmação)

Já coberto desde a Fase 3: `worker-market-data` roda 24/7, independente de haver operação, coletando candles reais continuamente. Nenhum trabalho adicional necessário — apenas confirmar, ao subir na VPS, que o container está de fato rodando e a tabela `market_data` crescendo (ver checklist em `docs/VPS_DEPLOY.md`).

## FASE 20 — VPS

Documentado em detalhe em [`docs/VPS_DEPLOY.md`](VPS_DEPLOY.md) — firewall, sincronização de relógio, backups, TLS, e o checklist de verificação pós-deploy. Estas ações exigem acesso real à sua VPS e não podem ser executadas por mim.

## Testes: 171/171 passando (backend). Frontend: build de produção limpo (`npm run build`), testado manualmente no browser contra a API real.

## Resumo do que ficou pendente (nenhuma fase do documento — só refinamentos)

1. **`alembic upgrade head` nunca rodou contra Postgres real** — só contra SQLite nos testes. Prioridade #1 ao chegar na VPS.
2. **`can_withdraw: True` na API key real da Binance** — ainda não resolvido (achado da Fase 2).
3. **Nenhuma ordem real foi enviada pelo sistema** — só o script manual `place_real_test_order.py` está pronto para isso, aguardando você rodar.
4. Gráficos/histórico no dashboard, tema, paginação — polimento de UI, não bloqueante.
5. Sincronização via User Data Stream autenticado (websocket) — hoje tudo é consultado via REST a cada ciclo do `worker-execution`; funciona, mas WS reduziria latência e uso de rate limit.

## Como continuar

Com todas as 23 fases do documento implementadas e testadas (171 testes automatizados + verificação manual do dashboard), o próximo passo natural é validar tudo junto na VPS: rodar `alembic upgrade head` contra o Postgres real, subir os containers, deixar `TRADING_MODE=paper` rodando por um tempo observando os logs e o dashboard, e só então considerar `testnet`/`live` — sempre com decisão explícita sua.
