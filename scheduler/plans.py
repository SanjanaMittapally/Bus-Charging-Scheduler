from scheduler.models import RouteConfig


def valid_charging_plans(route: RouteConfig, direction: str) -> list[list[str]]:
    distances = route.cumulative_distances(direction)
    charging_stations = [
        stop for stop in route.charging_stations if stop in distances
    ]
    if direction == "KB":
        charging_stations = sorted(
            charging_stations, key=lambda stop: distances[stop], reverse=False
        )

    origin = route.stops[0] if direction == "BK" else route.stops[-1]
    destination = route.stops[-1] if direction == "BK" else route.stops[0]
    total = distances[destination]
    range_km = route.battery_range_km

    def extend_paths(
        current_pos: int, remaining: list[str]
    ) -> list[list[str]]:
        if current_pos + range_km >= total:
            return [[]]

        paths: list[list[str]] = []
        for index, station in enumerate(remaining):
            station_pos = distances[station]
            if station_pos - current_pos > range_km:
                continue
            for tail in extend_paths(station_pos, remaining[index + 1 :]):
                paths.append([station] + tail)
        return paths

    plans = extend_paths(distances[origin], charging_stations)
    unique = []
    seen = set()
    for plan in plans:
        key = tuple(plan)
        if key not in seen:
            seen.add(key)
            unique.append(plan)
    return unique


def plan_legs(route: RouteConfig, direction: str, plan: list[str]) -> list[tuple[str, str, int]]:
    distances = route.cumulative_distances(direction)
    origin = route.stops[0] if direction == "BK" else route.stops[-1]
    destination = route.stops[-1] if direction == "BK" else route.stops[0]

    stops = [origin, *plan, destination]
    legs = []
    for start, end in zip(stops, stops[1:]):
        legs.append((start, end, distances[end] - distances[start]))
    return legs
