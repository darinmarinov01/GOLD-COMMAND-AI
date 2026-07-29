# GOLD COMMAND AI (V1 Initial)

Production-oriented initial version of an automated XAUUSD analysis platform.

## What This V1 Does

- Generates a daily AI-ready market analysis before London session.
- Recalculates the analysis hourly during the main trading window.
- Uses a rule-based scoring engine over Macro + Structure + Flow.
- Exposes API endpoints for latest snapshot and on-demand generation.

## Current V1 Scope

- Backend: FastAPI service
- Engine: deterministic rule engine for bias/probability/verdict/setup
- Scheduler: 07:30 daily + hourly updates 08:30-22:30 (EET by default)
- Prompting: base prompt template for narrative generation

## Project Structure

```text
GOLD-COMMAND-AI/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes.py
│   │   ├── analyzers/
│   │   │   └── rule_engine.py
│   │   ├── collectors/
│   │   │   └── market_data.py
│   │   ├── scheduler/
│   │   │   └── jobs.py
│   │   ├── services/
│   │   │   └── analysis_service.py
│   │   ├── config.py
│   │   ├── main.py
│   │   └── models.py
│   └── requirements.txt
├── docs/
│   └── v1-scope.md
├── frontend/
│   └── README.md
├── prompts/
│   └── daily_analysis_prompt.md
└── .env.example
```

## Quick Start

1. Create virtual environment and install dependencies:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Start API:

```bash
uvicorn app.main:app --reload --port 8000
```

3. Open docs:

```text
http://localhost:8000/docs
```

## Frontend (Next.js)

Requirement: Node.js 18.18+ (Node.js 20+ recommended).

1. Start frontend dev server:

```bash
cd frontend
npm install
npm run dev
```

2. Open:

```text
http://localhost:3000
```

The dashboard consumes backend data from `http://localhost:8000/api/v1` by default.

## API Endpoints

- `GET /api/v1/health` - Health check
- `GET /api/v1/analysis/latest` - Returns latest analysis snapshot
- `POST /api/v1/analysis/generate` - Forces new snapshot generation
- `POST /api/v1/price/override` - Sets manual current price override
- `DELETE /api/v1/price/override` - Clears manual price override
- `GET /api/v1/providers/status?probe=true` - Returns provider diagnostics and current source state

## Example Output (Abbreviated)

```json
{
	"symbol": "XAUUSD",
	"current_price": 3402.45,
	"bias": "bull",
	"confidence": 84.7,
	"verdict": "wait",
	"probabilities": {
		"bull": 73.6,
		"range": 10.2,
		"bear": 16.2
	}
}
```

## Config

Copy `.env.example` to `.env` in repo root and adjust if needed:

- `TIMEZONE=Europe/Sofia`
- `DAILY_REPORT_HOUR=7`
- `DAILY_REPORT_MINUTE=30`
- `UPDATE_START_HOUR=8`
- `UPDATE_END_HOUR=22`
- `UPDATE_MINUTE=30`
- `PRICE_PROVIDER=twelvedata`
	- Options: `auto`, `twelvedata`, `polygon`, `yahoo`
- `PRICE_REQUEST_TIMEOUT_SEC=5.0`
- `TWELVEDATA_API_KEY=...`
- `TWELVEDATA_SYMBOL=XAU/USD`
- `TWELVEDATA_BASE_URL=https://api.twelvedata.com`
- `POLYGON_API_KEY=...`
- `POLYGON_TICKER=C:XAUUSD`
- `POLYGON_BASE_URL=https://api.polygon.io`

Price source behavior:

- `PRICE_PROVIDER=auto`: TwelveData -> Polygon -> Yahoo -> stub fallback.
- `PRICE_PROVIDER=twelvedata`: TwelveData -> Polygon -> Yahoo -> stub fallback.
- `PRICE_PROVIDER=polygon`: Polygon -> TwelveData -> Yahoo -> stub fallback.
- `PRICE_PROVIDER=yahoo`: Yahoo only -> stub fallback.

## Next Steps (V1.1)

- Wire real providers for XAUUSD, DXY, yields, calendar, and news.
- Add PostgreSQL persistence for history and backtest metrics.
- Add Telegram push on hourly signal changes.
- Add frontend dashboard (Next.js + charting).