# Architecture

## Approach

The scheduler uses **event-driven simulation** with two phases:

1. **Plan assignment** — enumerate all valid charging-station sequences for each direction, then greedily assign each bus the plan that spreads load across stations.
2. **Timeline simulation** — process bus arrivals at charging stations in time order. When a charger is free, the bus charges immediately; otherwise it joins a queue. When charging finishes, the next bus is picked using a **weighted priority score**.

This fits the problem because:

- Hard rules (range, route order, one charger) are enforced during plan generation and simulation.
- Soft rules (individual, operator, overall) only affect queue ordering when there is contention.
- New scenarios, routes, and weights are data-driven.

## Data structure

Each scenario is one JSON file that fully describes a scheduling run:

```json
{
  "id": "scenario_1",
  "name": "...",
  "description": "...",
  "route": {
    "stops": ["Bengaluru", "A", "B", "C", "D", "Kochi"],
    "segments_km": [100, 120, 100, 120, 100],
    "charging_stations": ["A", "B", "C", "D"],
    "battery_range_km": 240,
    "charge_time_minutes": 25,
    "speed_kmh": 60
  },
  "weights": { "individual": 1.0, "operator": 1.0, "overall": 1.0 },
  "buses": [
    { "id": "bus-BK-01", "operator": "kpn", "direction": "BK", "departure": "19:00" }
  ]
}
```

**Output** (in memory, shown in the UI):

- Per bus: charging stations, charge events (arrival, wait, start, end), total wait, final arrival.
- Per station: ordered list of buses that charged there.

## Anticipated changes and how the design handles them

| Future change | How the design handles it |
|---------------|---------------------------|
| More buses | Add entries to `buses` in a scenario file |
| New operator | Use a new `operator` string in bus data |
| New charging station | Add stop to `stops`, update `segments_km`, add to `charging_stations` |
| Different segment distance | Change `segments_km` in scenario |
| Multiple chargers at a station | Extend station config with `charger_count` (engine would read it) |
| New route | New `stops` and `segments_km` in scenario |
| Different battery range or charge time | Change `battery_range_km` or `charge_time_minutes` in route config |
| Different speed | Change `speed_kmh` |
| Per-scenario weights | Already in each scenario's `weights` block |
| Priority buses | Add optional `priority` field on bus; extend soft-rule scoring |
| Time-of-day electricity cost | Add optional cost per station/hour; extend plan-cost function |
| Driver shift limits | Add new hard rule class that validates timeline |

No engine rewrite is needed for the data-only rows — only small rule or engine hooks for new *behavior*.

## Change a weight

Edit the scenario JSON:

```json
"weights": {
  "individual": 1.0,
  "operator": 2.0,
  "overall": 1.0
}
```

The engine reads `scenario.weights` in `priority_score()` inside `scheduler/rules.py`. Queue order at busy stations changes when operator weight is raised (see Scenario 4).

## Add a new rule

**Hard rule example** — minimum charge level (future):

```python
class MinimumChargeRule(HardRule):
    name = "minimum_charge"

    def validate_leg(self, distance_km: int) -> bool:
        return distance_km <= self._range_km  # extend with partial-charge logic
```

**Soft rule example** — priority buses:

```python
class PriorityBusRule(SoftRule):
    name = "priority"

    def score(self, context, bus_id, operator, arrival_minute) -> float:
        priority = context.bus_priorities.get(bus_id, 0)
        return priority
```

Register in `build_soft_rules()` and include any new weight in the scenario `weights` block.

## Assumptions

- Speed is 60 km/h unless overridden in scenario route config.
- Charging always fills the battery to full in exactly 25 minutes.
- Buses can wait at a station until the charger is free.
- When multiple valid plans exist, the engine picks the one with the lowest projected station load, then fewest stops.
- Queue priority combines current wait, operator cumulative wait, and arrival time using scenario weights.

## What is not built

- No database or auth (not required).
- No maps or metrics dashboards (not required).
- Charger count is fixed at one per station via simulation logic; adding `charger_count` to route data would be the next step for that extension.
