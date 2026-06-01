# Bus Charging Scheduler

Python + Streamlit app that schedules electric bus charging along the Bengaluru–Kochi corridor.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open the URL shown in the terminal (usually http://localhost:8501).

## Change a weight

Edit the `weights` block in any scenario file under `data/scenarios/`:

```json
"weights": {
  "individual": 1.0,
  "operator": 2.0,
  "overall": 1.0
}
```

Reload the app and pick that scenario. Weights are read from the scenario data, not hardcoded in the engine.

## Add a new scenario

Create a new JSON file in `data/scenarios/` using the same structure as the existing files. Include route config, weights, and a `buses` list. The dropdown picks up all `.json` files automatically.

## Add a new rule

1. Add a class in `scheduler/rules.py` that extends `HardRule` or `SoftRule`.
2. Register soft rules in `build_soft_rules()` or wire hard validation into plan generation.
3. Use scenario weights for any tunable soft-rule factor.

See `ARCHITECTURE.md` for examples.

## Project layout

```
app.py                  Streamlit UI
scheduler/
  models.py             Data classes
  loader.py             Load scenario JSON files
  plans.py              Valid charging plan generation
  rules.py              Hard/soft rules and queue priority
  engine.py             Event-driven scheduler
data/scenarios/         Five scenario files
```

## Assumptions

- Travel speed is 60 km/h (1 km = 1 minute).
- Buses wait at a station when the single charger is busy.
- Direction is encoded as `BK` (Bengaluru→Kochi) or `KB` (Kochi→Bengaluru).
- Plan selection spreads load across stations before simulation resolves queues.

## Deploy

Push to a public GitHub repo and deploy on [Streamlit Community Cloud](https://streamlit.io/cloud). Set `app.py` as the entry point.
