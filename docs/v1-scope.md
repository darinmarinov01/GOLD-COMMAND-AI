# GOLD COMMAND AI - V1 Scope

## Objective
Build a production-oriented V1 that auto-generates a daily Gold analysis before London open and updates hourly.

## V1 Included
- FastAPI backend with analysis endpoints.
- Rule-based scoring engine (Macro + Structure + Flow).
- Scheduler for 07:30 EET daily report and hourly updates from 08:30 to 22:30.
- Prompt template for AI narrative generation.
- Project structure prepared for modular growth.

## V1 Deferred (V2+)
- Paid order-flow data integrations (Footprint, DOM, CVD, GEX).
- Persistent storage and analytics history.
- Telegram bot notifications.
- Full frontend dashboard implementation.

## Data Sources (Target)
- XAUUSD/GC price: TwelveData / Polygon / broker API.
- Macro proxies: DXY, US10Y, US2Y, Oil, Silver, VIX via market provider.
- Economic calendar: ForexFactory / TradingEconomics.
- COT: CFTC.
- Fed probability: CME FedWatch.
- News: Reuters / FXStreet / Kitco.

## Notes
Current collectors are stubbed with sample values to keep V1 executable without external paid feeds.
