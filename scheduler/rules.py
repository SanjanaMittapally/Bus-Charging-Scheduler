from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from scheduler.models import RouteConfig, Weights


@dataclass
class RuleContext:
    route: RouteConfig
    weights: Weights
    operator_waits: dict[str, list[float]]


class HardRule(ABC):
    name: str

    @abstractmethod
    def validate_leg(self, distance_km: int) -> bool:
        raise NotImplementedError


class RangeRule(HardRule):
    name = "battery_range"

    def __init__(self, route: RouteConfig) -> None:
        self._range_km = route.battery_range_km

    def validate_leg(self, distance_km: int) -> bool:
        return distance_km <= self._range_km


class SoftRule(ABC):
    name: str

    @abstractmethod
    def score(self, context: RuleContext, bus_id: str, operator: str, arrival_minute: float) -> float:
        raise NotImplementedError


class IndividualWaitRule(SoftRule):
    name = "individual"

    def score(self, context: RuleContext, bus_id: str, operator: str, arrival_minute: float) -> float:
        waits = context.operator_waits.get(operator, [])
        if not waits:
            return 0.0
        return sum(waits) / len(waits)


class OperatorFairnessRule(SoftRule):
    name = "operator"

    def score(self, context: RuleContext, bus_id: str, operator: str, arrival_minute: float) -> float:
        totals = {
            op: sum(values) for op, values in context.operator_waits.items() if values
        }
        if not totals:
            return 0.0
        max_total = max(totals.values())
        return totals.get(operator, 0.0) / max_total if max_total else 0.0


class OverallEfficiencyRule(SoftRule):
    name = "overall"

    def score(self, context: RuleContext, bus_id: str, operator: str, arrival_minute: float) -> float:
        return -arrival_minute


def build_soft_rules() -> list[SoftRule]:
    return [IndividualWaitRule(), OperatorFairnessRule(), OverallEfficiencyRule()]


def priority_score(
    context: RuleContext,
    bus_id: str,
    operator: str,
    arrival_minute: float,
    wait_minutes: float,
) -> float:
    weights = context.weights
    individual = wait_minutes
    operator_totals = {
        op: sum(values) for op, values in context.operator_waits.items() if values
    }
    operator_pressure = operator_totals.get(operator, 0.0)
    overall = -arrival_minute

    return (
        weights.individual * individual
        + weights.operator * operator_pressure
        + weights.overall * overall
    )
