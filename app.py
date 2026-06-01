import json
from pathlib import Path

import pandas as pd
import streamlit as st

from scheduler.engine import format_minute, run_scheduler
from scheduler.loader import load_scenario, list_scenarios

DIRECTION_LABELS = {
    "BK": "Bengaluru→Kochi",
    "KB": "Kochi→Bengaluru",
}


def scenario_label(path: Path) -> str:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return data["name"]


st.set_page_config(page_title="Bus Charging Scheduler", layout="wide")
st.title("Bus Charging Scheduler")

scenario_paths = list_scenarios()
labels = {scenario_label(path): path for path in scenario_paths}
selected_name = st.selectbox("Scenario", sorted(labels.keys()))
scenario = load_scenario(labels[selected_name])
result = run_scheduler(scenario)

st.subheader("Scenario input")
st.caption(scenario.description)
input_rows = [
    {
        "Bus ID": bus.id,
        "Operator": bus.operator,
        "Direction": DIRECTION_LABELS.get(bus.direction, bus.direction),
        "Departure": bus.departure,
    }
    for bus in scenario.buses
]
st.dataframe(pd.DataFrame(input_rows), use_container_width=True, hide_index=True)

with st.expander("Raw scenario data"):
    st.json(json.loads(labels[selected_name].read_text(encoding="utf-8")))

st.subheader("Per-bus timetable")
bus_rows = []
for schedule in result.bus_schedules:
    charge_summary = ", ".join(
        f"{event.station} (arrive {format_minute(event.arrival_minute)}, "
        f"wait {event.wait_minutes:.0f} min, "
        f"charge {format_minute(event.charge_start_minute)}–{format_minute(event.charge_end_minute)})"
        for event in schedule.charge_events
    )
    bus_rows.append(
        {
            "Bus ID": schedule.bus_id,
            "Operator": schedule.operator,
            "Direction": DIRECTION_LABELS.get(schedule.direction, schedule.direction),
            "Departure": schedule.departure,
            "Charging stations": " → ".join(schedule.charging_stations),
            "Charge timeline": charge_summary,
            "Total wait (min)": round(schedule.total_wait_minutes, 1),
            "Final arrival": format_minute(schedule.arrival_minute),
        }
    )
st.dataframe(pd.DataFrame(bus_rows), use_container_width=True, hide_index=True)

st.subheader("Per-station view")
for station in scenario.route.charging_stations:
    st.markdown(f"**Station {station}**")
    slots = result.station_schedules.get(station, [])
    if not slots:
        st.write("No charging events.")
        continue
    station_rows = [
        {
            "Order": index + 1,
            "Bus ID": slot.bus_id,
            "Operator": slot.operator,
            "Arrival": format_minute(slot.arrival_minute),
            "Wait (min)": round(slot.wait_minutes, 1),
            "Charge start": format_minute(slot.charge_start_minute),
            "Charge end": format_minute(slot.charge_end_minute),
        }
        for index, slot in enumerate(slots)
    ]
    st.dataframe(pd.DataFrame(station_rows), use_container_width=True, hide_index=True)
