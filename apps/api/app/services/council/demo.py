"""Run one council round and print the debate. Works offline (no API keys needed).

Usage (from apps/api):
    python -m app.services.council.demo            # synthetic snapshot
    python -m app.services.council.demo --live btc # real Bitget snapshot (needs network)
"""

from __future__ import annotations

import argparse
import asyncio
import time

import httpx

from app.adapters.bitget.rest import BitgetRestClient
from app.adapters.coingecko.rest import CoinGeckoClient
from app.config import SYMBOL_MAP, get_settings
from app.domain.enums import DataSource
from app.domain.models import Ema, Indicators, Macd, MarketSnapshot
from app.services.council.graph import Council
from app.services.llm.client import LLMClient
from app.services.market.service import MarketService


def _synthetic(symbol: str = "BTCUSDT") -> MarketSnapshot:
    return MarketSnapshot(
        symbol=symbol, price=67250.0, change24h=2.6, high24h=68100.0, low24h=65400.0,
        base_volume=18234.5, quote_volume=1_223_000_000.0, volatility=0.31,
        indicators=Indicators(
            rsi=61.4,
            macd=Macd(macd=145.2, signal=98.7, histogram=46.5),
            ema=Ema(ema12=66980.0, ema26=66510.0, ema50=65980.0),
        ),
        ts=int(time.time() * 1000), source=DataSource.BITGET,
    )


async def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", help="symbol key for real Bitget data, e.g. btc")
    args = parser.parse_args()

    settings = get_settings()
    async with httpx.AsyncClient(timeout=settings.http_timeout_sec) as http:
        llm = LLMClient(http, settings)

        if args.live:
            svc = MarketService(
                BitgetRestClient(http, settings.bitget_rest_base),
                CoinGeckoClient(http, settings.coingecko_base, settings.coingecko_api_key),
                settings,
            )
            snapshot = await svc.get_snapshot(SYMBOL_MAP.get(args.live, "BTCUSDT"))
        else:
            snapshot = _synthetic()

        council = Council(llm)
        result = await council.run_round(snapshot)

    print(f"\n{'='*70}\nLIVE COUNCIL SESSION — {snapshot.symbol} @ {snapshot.price}")
    print(f"mode: {'OFFLINE (data-driven)' if llm.is_offline else 'LLM'}\n{'='*70}")
    for m in result["messages"]:
        refs = f"  ↪ to {', '.join(r.value for r in m.references)}" if m.references else ""
        print(f"\n[{m.agent_id.value.upper():9}] ({m.stance.value}, conf {m.confidence:.0f}){refs}")
        print(f"  {m.text}")

    print(f"\n{'-'*70}\nVOTES: " + ", ".join(f"{v.agent_id.value}={v.side.value}" for v in result["votes"]))
    rec = result["recommendation"]
    bd = result["confidence_breakdown"]
    print(f"CONFIDENCE: {rec.confidence}/100  "
          f"(agreement {bd.agreement} · risk {bd.risk} · vol {bd.volatility} · sentiment {bd.sentiment})")
    if rec.vetoed:
        print(f"\n*** COUNCIL DECISION BLOCKED ***  {rec.veto_reason}")
    else:
        print(f"\nFINAL RECOMMENDATION: {rec.side.value}  — {rec.summary}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(_main())
