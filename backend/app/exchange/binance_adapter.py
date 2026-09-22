"""Binance Spot ExchangeAdapter (instrucao.md #53).

Uses `binance-sdk-spot`, the official Binance-maintained SDK (verified 2026-09-22:
the older `binance-connector` package was archived/deprecated by Binance in April 2026).

Fase 2 scope: read-only operations only. create_order/cancel_order raise
NotImplementedError until Fase 8 implements client_order_id idempotency (instrucao.md #45, #46).
"""
from __future__ import annotations

from decimal import Decimal

from binance_common.configuration import ConfigurationRestAPI
from binance_common.constants import SPOT_REST_API_PROD_URL, SPOT_REST_API_TESTNET_URL
from binance_sdk_spot.spot import Spot

from app.core.config import Settings, TradingMode
from app.exchange.base import ExchangeAdapter
from app.exchange.types import (
    AccountBalance,
    AccountInfo,
    BestBidAsk,
    Candle,
    CommissionRates,
    OrderInfo,
    SymbolRules,
    TradeFill,
)


def _d(value: object) -> Decimal:
    """Convert an exchange-returned numeric (str/float/int) to Decimal safely."""
    return Decimal(str(value))


class BinanceExchangeAdapter(ExchangeAdapter):
    def __init__(self, settings: Settings) -> None:
        base_path = (
            SPOT_REST_API_PROD_URL
            if settings.trading_mode is TradingMode.LIVE
            else SPOT_REST_API_TESTNET_URL
        )
        config = ConfigurationRestAPI(
            api_key=settings.binance_api_key,
            api_secret=settings.binance_api_secret,
            base_path=base_path,
        )
        self._client = Spot(config_rest_api=config)
        self._symbol_rules_cache: dict[str, SymbolRules] = {}

    def get_server_time(self) -> int:
        response = self._client.rest_api.time()
        return response.data().server_time

    def get_account(self) -> AccountInfo:
        response = self._client.rest_api.get_account()
        data = response.data()
        balances = [
            AccountBalance(asset=b.asset, free=_d(b.free), locked=_d(b.locked))
            for b in (data.balances or [])
        ]
        return AccountInfo(
            can_trade=bool(data.can_trade),
            can_withdraw=bool(data.can_withdraw),
            can_deposit=bool(data.can_deposit),
            balances=balances,
            update_time=data.update_time,
        )

    def get_balances(self) -> list[AccountBalance]:
        return self.get_account().balances

    def get_symbol_info(self, symbol: str) -> SymbolRules:
        if symbol in self._symbol_rules_cache:
            return self._symbol_rules_cache[symbol]

        response = self._client.rest_api.exchange_info(symbol=symbol)
        data = response.data()
        if not data.symbols:
            raise ValueError(f"symbol not found on exchange: {symbol}")
        info = data.symbols[0]

        tick_size: Decimal | None = None
        step_size: Decimal | None = None
        min_qty: Decimal | None = None
        max_qty: Decimal | None = None
        min_notional: Decimal | None = None
        max_notional: Decimal | None = None

        for f in info.filters or []:
            filter_type = getattr(f.actual_instance, "filter_type", None)
            inst = f.actual_instance
            if filter_type == "PRICE_FILTER":
                tick_size = _d(inst.tick_size)
            elif filter_type == "LOT_SIZE":
                step_size = _d(inst.step_size)
                min_qty = _d(inst.min_qty)
                max_qty = _d(inst.max_qty)
            elif filter_type in ("NOTIONAL", "MIN_NOTIONAL"):
                min_notional = _d(getattr(inst, "min_notional", None)) if getattr(inst, "min_notional", None) is not None else None
                max_notional_raw = getattr(inst, "max_notional", None)
                max_notional = _d(max_notional_raw) if max_notional_raw is not None else None

        if tick_size is None or step_size is None or min_qty is None or max_qty is None:
            raise ValueError(f"exchange did not return required filters for symbol: {symbol}")

        rules = SymbolRules(
            symbol=info.symbol,
            status=str(info.status),
            base_asset=info.base_asset,
            quote_asset=info.quote_asset,
            tick_size=tick_size,
            step_size=step_size,
            min_qty=min_qty,
            max_qty=max_qty,
            min_notional=min_notional,
            max_notional=max_notional,
            is_spot_trading_allowed=bool(info.is_spot_trading_allowed),
        )
        self._symbol_rules_cache[symbol] = rules
        return rules

    def get_commissions(self, symbol: str) -> CommissionRates:
        response = self._client.rest_api.account_commission(symbol=symbol)
        data = response.data()
        return CommissionRates(
            symbol=data.symbol,
            maker=_d(data.standard_commission.maker),
            taker=_d(data.standard_commission.taker),
        )

    def get_best_bid_ask(self, symbol: str) -> BestBidAsk:
        response = self._client.rest_api.ticker_book_ticker(symbol=symbol)
        data = response.data().actual_instance
        return BestBidAsk(
            symbol=data.symbol,
            bid_price=_d(data.bid_price),
            bid_qty=_d(data.bid_qty),
            ask_price=_d(data.ask_price),
            ask_qty=_d(data.ask_qty),
        )

    def get_klines(
        self,
        symbol: str,
        interval: str,
        *,
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int = 1000,
    ) -> list[Candle]:
        response = self._client.rest_api.klines(
            symbol=symbol,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )
        rows = response.data()
        candles = []
        for row in rows:
            (
                open_time, open_, high, low, close, volume, close_time,
                quote_volume, trade_count, taker_buy_base, taker_buy_quote, _ignore,
            ) = row
            candles.append(
                Candle(
                    symbol=symbol,
                    interval=interval,
                    open_time=int(open_time),
                    close_time=int(close_time),
                    open=_d(open_),
                    high=_d(high),
                    low=_d(low),
                    close=_d(close),
                    volume=_d(volume),
                    quote_volume=_d(quote_volume),
                    trade_count=int(trade_count),
                    taker_buy_base_volume=_d(taker_buy_base),
                    taker_buy_quote_volume=_d(taker_buy_quote),
                )
            )
        return candles

    def get_open_orders(self, symbol: str) -> list[OrderInfo]:
        response = self._client.rest_api.get_open_orders(symbol=symbol)
        return [self._to_order_info(o) for o in response.data()]

    def get_order(
        self, symbol: str, *, client_order_id: str | None = None, exchange_order_id: str | None = None
    ) -> OrderInfo:
        kwargs: dict[str, object] = {"symbol": symbol}
        if client_order_id is not None:
            kwargs["orig_client_order_id"] = client_order_id
        if exchange_order_id is not None:
            kwargs["order_id"] = int(exchange_order_id)
        response = self._client.rest_api.get_order(**kwargs)
        return self._to_order_info(response.data())

    def get_recent_orders(self, symbol: str, limit: int = 50) -> list[OrderInfo]:
        response = self._client.rest_api.all_orders(symbol=symbol, limit=limit)
        return [self._to_order_info(o) for o in response.data()]

    def get_trades(self, symbol: str, limit: int = 50) -> list[TradeFill]:
        response = self._client.rest_api.my_trades(symbol=symbol, limit=limit)
        fills = []
        for t in response.data():
            fills.append(
                TradeFill(
                    exchange_trade_id=str(t.id),
                    exchange_order_id=str(t.order_id),
                    symbol=t.symbol,
                    price=_d(t.price),
                    quantity=_d(t.qty),
                    commission=_d(t.commission),
                    commission_asset=t.commission_asset,
                    is_buyer=bool(t.is_buyer),
                    timestamp=t.time,
                )
            )
        return fills

    def create_order(
        self,
        *,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        client_order_id: str,
        price: Decimal | None = None,
    ) -> OrderInfo:
        """instrucao.md #45-#47. Sends Decimal straight through (never float) so the
        exact quantity string reaches the exchange — the SDK stringifies floats via
        str(), which can silently mis-round or emit scientific notation for small
        step sizes; Decimal.__str__ is always exact."""
        kwargs: dict[str, object] = dict(
            symbol=symbol,
            side=side,
            type=order_type,
            quantity=quantity,
            new_client_order_id=client_order_id,
        )
        if order_type == "LIMIT":
            if price is None:
                raise ValueError("LIMIT orders require a price")
            kwargs["price"] = price
            kwargs["time_in_force"] = "GTC"

        response = self._client.rest_api.new_order(**kwargs)
        return self._to_order_info(response.data(), time_field="transact_time")

    def cancel_order(
        self, symbol: str, *, client_order_id: str | None = None, exchange_order_id: str | None = None
    ) -> OrderInfo:
        kwargs: dict[str, object] = {"symbol": symbol}
        if client_order_id is not None:
            kwargs["orig_client_order_id"] = client_order_id
        if exchange_order_id is not None:
            kwargs["order_id"] = int(exchange_order_id)
        response = self._client.rest_api.delete_order(**kwargs)
        return self._to_order_info(response.data(), time_field="transact_time")

    @staticmethod
    def _to_order_info(o, *, time_field: str = "update_time") -> OrderInfo:
        return OrderInfo(
            exchange_order_id=str(o.order_id),
            client_order_id=o.client_order_id,
            symbol=o.symbol,
            side=str(o.side),
            order_type=str(o.type),
            status=str(o.status),
            price=_d(o.price),
            orig_qty=_d(o.orig_qty),
            executed_qty=_d(o.executed_qty),
            update_time=getattr(o, time_field),
            raw=o.to_dict() if hasattr(o, "to_dict") else {},
        )
