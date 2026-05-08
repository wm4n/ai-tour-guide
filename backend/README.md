# Tour Guide Backend

## Setup

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # then edit with your GEMINI_API_KEY
```

## Run

```bash
uvicorn tour_guide.main:app --reload
```

## Test

```bash
pytest                            # unit + integration (offline)
pytest -m real_provider           # smoke test against real Gemini (costs $)
```
