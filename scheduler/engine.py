from __future__ import annotations

import heapq
from dataclasses import dataclass, field

from scheduler.models import (
    BusInput,
    BusSchedule,
    ChargeEvent,
    RouteConfig,
    Scenario,
    ScheduleResult,
    StationSlot,
)
from scheduler.plans import plan_legs, valid_charging_plans
from scheduler.rules import RuleContext, priority_score


def _parse_time_to_minutes(value: str) -> float:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def _minutes_to_time(value: float) -> str:
    total = int(round(value))
    return f"{(total // 60) % 24:02d}:{total % 60:02d}"


def format_minute(value: float) -> str:
    return _minutes_to_time(value)


@dataclass
class BusRun:
    bus: BusInput
    plan: list[str]
    legs: list[tuple[str, str, int]]
    charge_events: list[ChargeEvent] = field(default_factory=list)
    total_wait_minutes: float = 0.0
    arrival_minute: float = 0.0


@dataclass
class WaitingBus:
    bus_id: str
    operator: str
    arrival_minute: float
    leg_index: int


@dataclass
class StationState:
    busy_until: float = 0.0
    queue: list[WaitingBus] = field(default_factory=list)


@dataclass(order=True)
class Event:
    time: float
    order: int
    kind: str = field(compare=False)
    bus_id: str = field(compare=False)
    leg_index: int = field(compare=False)
    station: str = field(compare=False)


def _estimate_plan_load(
    route: RouteConfig,
    direction: str,
    plan: list[str],
    departure_minute: float,
) -> dict[str, float]:
    load: dict[str, float] = {}
    current = departure_minute
    for _, end, distance in plan_legs(route, direction, plan):
        current += route.travel_minutes(distance)
        if end in route.charging_stations:
            load[end] = load.get(end, 0.0) + 1.0
    return load


def _choose_plan(
    route: RouteConfig,
    bus: BusInput,
    plans: list[list[str]],
    station_load: dict[str, float],
) -> list[str]:
    departure = _parse_time_to_minutes(bus.departure)

    def plan_cost(plan: list[str]) -> tuple[float, int]:
        projected = dict(station_load)
        for station, value in _estimate_plan_load(route, bus.direction, plan, departure).items():
            projected[station] = projected.get(station, 0.0) + value
        return (sum(projected.values()), len(plan))

    return min(plans, key=plan_cost)


def _record_charge(
    run: BusRun,
    station: str,
    arrival: float,
    charge_start: float,
    route: RouteConfig,
) -> float:
    wait = max(0.0, charge_start - arrival)
    charge_end = charge_start + route.charge_time_minutes
    run.total_wait_minutes += wait
    run.charge_events.append(
        ChargeEvent(
            station=station,
            arrival_minute=arrival,
            wait_minutes=wait,
            charge_start_minute=charge_start,
            charge_end_minute=charge_end,
        )
    )
    return charge_end


def _pick_next(
    queue: list[WaitingBus],
    context: RuleContext,
    now: float,
) -> WaitingBus:
    queue.sort(
        key=lambda item: priority_score(
            context,
            item.bus_id,
            item.operator,
            item.arrival_minute,
            max(0.0, now - item.arrival_minute),
        ),
        reverse=True,
    )
    return queue.pop(0)


def _push(events: list[Event], order: list[int], event: Event) -> None:
    order[0] += 1
    heapq.heappush(events, Event(event.time, order[0], event.kind, event.bus_id, event.leg_index, event.station))


def _schedule_leg_arrival(
    run: BusRun,
    leg_index: int,
    start_minute: float,
    route: RouteConfig,
    events: list[Event],
    order: list[int],
) -> None:
    _, end, distance = run.legs[leg_index]
    arrival = start_minute + route.travel_minutes(distance)
    _push(
        events,
        order,
        Event(arrival, 0, "arrive", run.bus.id, leg_index, end if end in route.charging_stations else ""),
    )


def _start_charge(
    run: BusRun,
    station_name: str,
    station: StationState,
    arrival: float,
    leg_index: int,
    route: RouteConfig,
    operator_waits: dict[str, list[float]],
    events: list[Event],
    order: list[int],
) -> None:
    charge_start = max(arrival, station.busy_until)
    charge_end = _record_charge(run, station_name, arrival, charge_start, route)
    operator_waits.setdefault(run.bus.operator, []).append(run.charge_events[-1].wait_minutes)
    station.busy_until = charge_end
    _push(events, order, Event(charge_end, 0, "charge_done", run.bus.id, leg_index, station_name))

    next_leg = leg_index + 1
    if next_leg < len(run.legs):
        _schedule_leg_arrival(run, next_leg, charge_end, route, events, order)


def _process_queue(
    station_name: str,
    station: StationState,
    runs: dict[str, BusRun],
    route: RouteConfig,
    scenario: Scenario,
    operator_waits: dict[str, list[float]],
    events: list[Event],
    order: list[int],
) -> None:
    if not station.queue:
        return

    context = RuleContext(route, scenario.weights, operator_waits)
    next_item = _pick_next(station.queue, context, station.busy_until)
    next_run = runs[next_item.bus_id]
    _start_charge(
        next_run,
        station_name,
        station,
        next_item.arrival_minute,
        next_item.leg_index,
        route,
        operator_waits,
        events,
        order,
    )


def run_scheduler(scenario: Scenario) -> ScheduleResult:
    route = scenario.route
    plans_by_direction = {
        direction: valid_charging_plans(route, direction)
        for direction in {bus.direction for bus in scenario.buses}
    }
    station_load = {stop: 0.0 for stop in route.charging_stations}

    runs: dict[str, BusRun] = {}
    for bus in sorted(scenario.buses, key=lambda item: _parse_time_to_minutes(item.departure)):
        plan = _choose_plan(route, bus, plans_by_direction[bus.direction], station_load)
        for station, value in _estimate_plan_load(
            route, bus.direction, plan, _parse_time_to_minutes(bus.departure)
        ).items():
            station_load[station] = station_load.get(station, 0.0) + value
        runs[bus.id] = BusRun(
            bus=bus,
            plan=plan,
            legs=plan_legs(route, bus.direction, plan),
        )

    stations = {name: StationState() for name in route.charging_stations}
    operator_waits: dict[str, list[float]] = {}
    events: list[Event] = []
    order = [0]

    for run in runs.values():
        _schedule_leg_arrival(
            run,
            0,
            _parse_time_to_minutes(run.bus.departure),
            route,
            events,
            order,
        )

    while events:
        event = heapq.heappop(events)
        run = runs[event.bus_id]

        if event.kind == "charge_done":
            _process_queue(
                event.station,
                stations[event.station],
                runs,
                route,
                scenario,
                operator_waits,
                events,
                order,
            )
            continue

        _, end, _ = run.legs[event.leg_index]
        arrival = event.time

        if end not in route.charging_stations:
            run.arrival_minute = arrival
            continue

        station = stations[end]
        if station.busy_until <= arrival:
            _start_charge(
                run,
                end,
                station,
                arrival,
                event.leg_index,
                route,
                operator_waits,
                events,
                order,
            )
        else:
            station.queue.append(
                WaitingBus(
                    bus_id=run.bus.id,
                    operator=run.bus.operator,
                    arrival_minute=arrival,
                    leg_index=event.leg_index,
                )
            )

    bus_schedules = [
        BusSchedule(
            bus_id=run.bus.id,
            operator=run.bus.operator,
            direction=run.bus.direction,
            departure=run.bus.departure,
            charging_stations=run.plan,
            charge_events=run.charge_events,
            arrival_minute=run.arrival_minute,
            total_wait_minutes=run.total_wait_minutes,
        )
        for run in runs.values()
    ]

    station_schedules: dict[str, list[StationSlot]] = {
        stop: [] for stop in route.charging_stations
    }
    for schedule in bus_schedules:
        for charge in schedule.charge_events:
            station_schedules[charge.station].append(
                StationSlot(
                    bus_id=schedule.bus_id,
                    operator=schedule.operator,
                    arrival_minute=charge.arrival_minute,
                    wait_minutes=charge.wait_minutes,
                    charge_start_minute=charge.charge_start_minute,
                    charge_end_minute=charge.charge_end_minute,
                )
            )
    for slots in station_schedules.values():
        slots.sort(key=lambda slot: slot.charge_start_minute)

    return ScheduleResult(
        scenario=scenario,
        bus_schedules=sorted(bus_schedules, key=lambda item: item.bus_id),
        station_schedules=station_schedules,
    )
