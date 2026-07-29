from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "GOLD COMMAND AI"
    environment: str = "dev"
    timezone: str = "Europe/Sofia"

    # Daily report before London open.
    daily_report_hour: int = 7
    daily_report_minute: int = 30

    # Hourly updates from 08:30 to 22:30.
    update_start_hour: int = 8
    update_end_hour: int = 22
    update_minute: int = 30

    # Live price provider settings.
    # Supported values: auto, twelvedata, polygon, yahoo
    price_provider: str = "auto"
    price_request_timeout_sec: float = 5.0

    twelvedata_api_key: str = ""
    twelvedata_symbol: str = "XAU/USD"
    twelvedata_base_url: str = "https://api.twelvedata.com"

    polygon_api_key: str = ""
    polygon_ticker: str = "C:XAUUSD"
    polygon_base_url: str = "https://api.polygon.io"

    # Goldbach/IPDA range configuration
    goldbach_po3_range: float = 27.0
    goldbach_use_pips: bool = False
    goldbach_tick_size: float = 0.25
    goldbach_manual_range_low: float = 0.0
    goldbach_manual_range_high: float = 0.0

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), env_file_encoding="utf-8")


settings = Settings()
