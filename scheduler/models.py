from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Weights:
    individual: float = 1.0
    operator: float = 1.0
    overall: float = 1.0


@dataclass(frozen=True)
class RouteConfig:
    stops: list[str]
    segments_km: list[int]
    charging_stations: list[str]
    battery_range_km: int = 240
    charge_time_minutes: int = 25
    speed_kmh: float = 60.0

    @property
    def total_distance_km(self) -> int:
        return sum(self.segments_km)

    def cumulative_distances(self, direction: str) -> dict[str, int]:
        if direction == "BK":
            ordered = self.stops
        else:
            ordered = list(reversed(self.stops))

        distances: dict[str, int] = {}
        total = 0
        for stop in ordered:
            distances[stop] = total
            idx = self.stops.index(stop)
            if direction == "BK" and stop != self.stops[-1]:
                total += self.segments_km[idx]
            elif direction == "KB" and stop != self.stops[0]:
                seg_idx = idx - 1
                total += self.segments_km[seg_idx]
        return distances

    def travel_minutes(self, distance_km: int) -> float:
        return distance_km / self.speed_kmh * 60.0


@dataclass(frozen=True)
class BusInput:
    id: str
    operator: str
    direction: str
    departure: str


@dataclass(frozen=True)
class Scenario:
    id: str
    name: str
    description: str
    route: RouteConfig
    weights: Weights
    buses: list[BusInput]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Scenario:
        route_data = data["route"]
        route = RouteConfig(
            stops=route_data["stops"],
            segments_km=route_data["segments_km"],
            charging_stations=route_data["charging_stations"],
            battery_range_km=route_data.get("battery_range_km", 240),
            charge_time_minutes=route_data.get("charge_time_minutes", 25),
            speed_kmh=route_data.get("speed_kmh", 60.0),
        )
        weights_data = data.get("weights", {})
        weights = Weights(
            individual=weights_data.get("individual", 1.0),
            operator=weights_data.get("operator", 1.0),
            overall=weights_data.get("overall", 1.0),
        )
        buses = [
            BusInput(
                id=bus["id"],
                operator=bus["operator"],
                direction=bus["direction"],
                departure=bus["departure"],
            )
            for bus in data["buses"]
        ]
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            route=route,
            weights=weights,
            buses=buses,
        )


@dataclass
class ChargeEvent:
    station: str
    arrival_minute: float
    wait_minutes: float
    charge_start_minute: float
    charge_end_minute: float


@dataclass
class BusSchedule:
    bus_id: str
    operator: str
    direction: str
    departure: str
    charging_stations: list[str]
    charge_events: list[ChargeEvent]
    arrival_minute: float
    total_wait_minutes: float

    @property
    def destination(self) -> str:
        return "Kochi" if self.direction == "BK" else "Bengaluru"

    @property
    def origin(self) -> str:
        return "Bengaluru" if self.direction == "BK" else "Kochi"


@dataclass
class StationSlot:
    bus_id: str
    operator: str
    arrival_minute: float
    wait_minutes: float
    charge_start_minute: float
    charge_end_minute: float


@dataclass
class ScheduleResult:
    scenario: Scenario
    bus_schedules: list[BusSchedule]
    station_schedules: dict[str, list[StationSlot]] = field(default_factory=dict)
