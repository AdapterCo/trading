"""Out-of-sample splitting (instrucao.md #101). Chronological only — never shuffled,
since shuffling a time series would leak future information into training.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.exchange.types import Candle


@dataclass(frozen=True)
class DataSplit:
    train: list[Candle]
    validation: list[Candle]
    test: list[Candle]


def split_chronologically(candles: list[Candle], *, train_ratio: float, validation_ratio: float) -> DataSplit:
    """instrucao.md #101 — TEST never participates in parameter selection.
    Splits are purely chronological: train is the oldest slice, test the newest.
    """
    if not (0 < train_ratio < 1) or not (0 <= validation_ratio < 1) or train_ratio + validation_ratio >= 1:
        raise ValueError("train_ratio + validation_ratio must be < 1, both must be valid fractions")

    n = len(candles)
    train_end = int(n * train_ratio)
    validation_end = train_end + int(n * validation_ratio)

    return DataSplit(
        train=candles[:train_end],
        validation=candles[train_end:validation_end],
        test=candles[validation_end:],
    )
