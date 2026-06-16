"""Application configuration loaded from environment variables.

Uses pydantic-settings so every value is typed and validated at startup.
Market endpoints are public (no key needed); LLM/Supabase keys arrive in later steps.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- Server -------------------------------------------------------------
    app_env: str = "development"
    port: int = 8000
    # Comma-separated list in the env; parsed into a list below.
    allowed_origins: str = "http://localhost:3000"

    # ---- Market data sources (public, unauthenticated) ----------------------
    bitget_rest_base: str = "https://api.bitget.com"
    bitget_ws_public: str = "wss://ws.bitget.com/v2/ws/public"
    coingecko_base: str = "https://api.coingecko.com/api/v3"
    coingecko_api_key: str | None = None

    # ---- Indicator / candle settings ---------------------------------------
    candle_granularity: str = "15min"  # Bitget v2 spot: 1min/5min/15min/30min/1h/4h...
    candle_limit: int = Field(default=200, ge=60, le=1000)

    # ---- Caching ------------------------------------------------------------
    snapshot_ttl_sec: float = 3.0  # serve cached snapshot within this window
    candle_cache_ttl_sec: float = 15.0  # candles change slowly; cache longer

    # ---- HTTP client --------------------------------------------------------
    http_timeout_sec: float = 8.0

    # ---- LLM: Qwen primary, OpenAI fallback --------------------------------
    # If no key is configured the council runs in data-driven OFFLINE mode:
    # agents reason deterministically over the REAL market snapshot/indicators.
    qwen_api_key: str | None = None
    qwen_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-plus"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 400
    llm_timeout_sec: float = 30.0

    # ---- Ambient council session + streaming cadence -----------------------
    council_symbol: str = "BTCUSDT"            # the always-on session subject
    council_round_interval_sec: float = 6.0    # pause between completed rounds
    cadence_tokens_per_sec: float = 18.0       # word-by-word streaming pace
    thinking_pause_sec: float = 0.7            # how long "thinking" shows before tokens

    # ---- Supabase (Trade Journal persistence) ------------------------------
    # If unset, the journal degrades to a no-op (the app still runs in dev).
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


# Maps the friendly path segment (/market/btc) to a Bitget spot symbol.
SYMBOL_MAP: dict[str, str] = {
    "btc": "BTCUSDT",
    "eth": "ETHUSDT",
    "sol": "SOLUSDT",
    "xrp": "XRPUSDT",
    "doge": "DOGEUSDT",
}

# Reverse lookup + the canonical list the WS consumer subscribes to.
SUPPORTED_SYMBOLS: list[str] = list(SYMBOL_MAP.values())

# CoinGecko fallback: Bitget symbol -> CoinGecko coin id.
COINGECKO_IDS: dict[str, str] = {
    "BTCUSDT": "bitcoin",
    "ETHUSDT": "ethereum",
    "SOLUSDT": "solana",
    "XRPUSDT": "ripple",
    "DOGEUSDT": "dogecoin",
}


@lru_cache
def get_settings() -> Settings:
    return Settings()
