"""Financial enums."""

from __future__ import annotations

from enum import Enum


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    SHORT = "SHORT"
    COVER = "COVER"


class AssetClass(str, Enum):
    EQUITY = "EQUITY"
    FIXED_INCOME = "FIXED_INCOME"
    FX = "FX"
    COMMODITY = "COMMODITY"
    DERIVATIVE = "DERIVATIVE"
    CRYPTO = "CRYPTO"
    CASH = "CASH"
    FUND = "FUND"
    REAL_ESTATE = "REAL_ESTATE"
    OTHER = "OTHER"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    MOC = "MOC"
    MOO = "MOO"
    LOC = "LOC"
    LOO = "LOO"


class TimeInForce(str, Enum):
    DAY = "DAY"
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"
    GTD = "GTD"
    OPG = "OPG"
    CLS = "CLS"


class SettlementType(str, Enum):
    DVP = "DVP"
    FOP = "FOP"
    CASH = "CASH"


class CorporateActionType(str, Enum):
    CASH_DIVIDEND = "CASH_DIVIDEND"
    STOCK_DIVIDEND = "STOCK_DIVIDEND"
    SPLIT = "SPLIT"
    REVERSE_SPLIT = "REVERSE_SPLIT"
    MERGER = "MERGER"
    SPINOFF = "SPINOFF"
    RIGHTS_ISSUE = "RIGHTS_ISSUE"
    TENDER_OFFER = "TENDER_OFFER"
