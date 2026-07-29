# Frontend Dashboard (Next.js)

The frontend is migrated to Next.js and now renders dynamic sections from backend snapshot data.

## Stack

- Next.js (App Router)
- React
- TypeScript

## Run

Prerequisite:

- Node.js 18.18+ (or 20+ recommended)

1. Start backend API:
	- `cd backend`
	- `uvicorn app.main:app --reload --port 8000`
2. Start frontend:
	- `cd frontend`
	- `npm install`
	- `npm run dev`
3. Open:
	- `http://localhost:3000`

## Dynamic Sections

- Price Terrain
- Sessions
- Confluence Matrix
- Limit Orders
- Probability Engine
- Score Breakdown
- Live Price Tape (TradingView Lightweight Charts)
- Hourly Timeline Diff (snapshot-to-snapshot changes)

## API

- Latest snapshot: `GET /api/v1/analysis/latest`
- Force generation: `POST /api/v1/analysis/generate`

## Environment

Optional:

- `NEXT_PUBLIC_API_BASE=http://localhost:8000/api/v1`

If not set, this is used as default.
