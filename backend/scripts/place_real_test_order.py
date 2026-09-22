"""Manual, operator-run script to send ONE real minimal BUY order (instrucao.md Fase 8).

This is intentionally NOT something the assistant runs — financial trades must be
executed by the operator themselves. Run it yourself:

    cd backend
    ./.venv/Scripts/python scripts/place_real_test_order.py            # dry run (default)
    ./.venv/Scripts/python scripts/place_real_test_order.py --execute  # sends the real order

Safety:
- TRADING_MODE in .env must be LIVE (this script refuses to run against paper/testnet
  configs, since the whole point is testing the REAL execution path — instrucao.md #5
  still applies: LIVE is never the .env.example default, but you set it deliberately).
- Requires --execute AND a typed "CONFIRMAR" to actually place the order.
- Order size is the smallest that clears the exchange's minNotional filter, capped
  at MAX_TEST_NOTIONAL_USDT below — this is a manual override for verification only,
  NOT driven by Strategy/RiskEngine sizing (equity is too small right now for the
  1% RISK_PER_TRADE to clear minNotional, per instrucao.md #27/#28).
- Runs through the exact same OrderIntentRepository -> OrderSender path production
  code will use, against a local SQLite file (no Postgres provisioned yet) so the
  audit trail (signals/order_intents/exchange_orders) is real and inspectable.
"""
from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import TradingMode, get_settings
from app.core.logging import configure_logging
from app.db.base import Base
from app.exchange.binance_adapter import BinanceExchangeAdapter
from app.execution.repository import ExchangeOrderRepository
from app.execution.sender import OrderSender
from app.orders.repository import OrderIntentRepository, SignalRepository
from app.risk.sizing import round_down_to_step
from app.risk.types import RiskDecision
from app.strategy.types import Signal, SignalDecision

MAX_TEST_NOTIONAL_USDT = Decimal("10")  # hard ceiling for this manual test, regardless of balance
NOTIONAL_SAFETY_MARGIN = Decimal("1.2")  # stay comfortably above minNotional


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Actually send the order (default: dry run only)")
    args = parser.parse_args()

    configure_logging()
    settings = get_settings()

    if settings.trading_mode is not TradingMode.LIVE:
        print(f"Refusing to run: TRADING_MODE is '{settings.trading_mode.value}', must be 'live'.")
        return 1

    exchange = BinanceExchangeAdapter(settings)

    account = exchange.get_account()
    if not account.can_trade:
        print("Refusing to run: account.can_trade is False.")
        return 1

    symbol_rules = exchange.get_symbol_info(settings.symbol)
    quote = exchange.get_best_bid_ask(settings.symbol)
    entry_price = quote.ask_price  # BUY crosses the spread, so this is the realistic fill price

    usdt_balance = next((b.free for b in account.balances if b.asset == settings.quote_asset), Decimal("0"))

    min_notional = symbol_rules.min_notional or Decimal("0")
    target_notional = min(min_notional * NOTIONAL_SAFETY_MARGIN, MAX_TEST_NOTIONAL_USDT)
    if target_notional > usdt_balance:
        print(f"Refusing to run: target notional {target_notional} {settings.quote_asset} exceeds "
              f"available balance {usdt_balance} {settings.quote_asset}.")
        return 1

    quantity = round_down_to_step(target_notional / entry_price, symbol_rules.step_size)
    quantity = max(quantity, symbol_rules.min_qty)
    notional = quantity * entry_price

    print("=== PLANO DE ORDEM DE TESTE (real, mainnet) ===")
    print(f"  symbol:          {settings.symbol}")
    print(f"  side:            BUY")
    print(f"  type:            MARKET")
    print(f"  quantity:        {quantity} {symbol_rules.base_asset}")
    print(f"  preco de ref.:   {entry_price} {settings.quote_asset} (best ask)")
    print(f"  notional aprox.: {notional} {settings.quote_asset}")
    print(f"  saldo USDT:      {usdt_balance}")
    print(f"  minNotional:     {min_notional}")

    if not args.execute:
        print("\nModo dry-run (padrao). Nenhuma ordem foi enviada.")
        print("Rode novamente com --execute para prosseguir ate a confirmacao.")
        return 0

    print("\nEsta e uma ordem REAL com dinheiro REAL. Não ha desfazer.")
    typed = input("Digite CONFIRMAR para enviar a ordem: ").strip()
    if typed != "CONFIRMAR":
        print("Confirmacao nao recebida. Abortando sem enviar nada.")
        return 1

    engine = create_engine("sqlite:///./manual_test_orders.db")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    signal = Signal(
        symbol=settings.symbol,
        strategy="ManualExecutionTest",
        strategy_version="1.0.0",
        decision=SignalDecision.BUY,
        reference_price=float(entry_price),
        candle_open_time=0,
        reasons=["MANUAL_OPERATOR_TEST_ORDER"],
        indicator_snapshot={},
    )
    SignalRepository(session).save(signal)

    decision = RiskDecision(
        approved=True,
        reasons=[],
        quantity=quantity,
        stop_price=entry_price,  # not a real stop for this manual test — Fase 11 handles real protection
        take_profit=entry_price,
        risk_amount=notional,
    )
    intent = OrderIntentRepository(session).create_from_decision(
        signal=signal, decision=decision, settings=settings, side="BUY", order_type="MARKET"
    )

    sender = OrderSender(exchange, ExchangeOrderRepository(session))
    result = sender.send(intent)

    print("\n=== RESULTADO ===")
    print(f"  client_order_id:   {result.client_order_id}")
    print(f"  exchange_order_id: {result.exchange_order_id}")
    print(f"  status:            {result.status}")
    print(f"  executed_qty:      {result.executed_qty}")
    print(f"  price:             {result.price}")
    print(f"\nRegistrado em backend/manual_test_orders.db (signals/order_intents/exchange_orders).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
