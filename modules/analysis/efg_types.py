"""Energy Flow Graph (EFG) data model.

Extracted from SMART-Dal/codegreen (MPL-2.0).
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class Accuracy(Enum):
    """Provenance of a number — never mistake a guess for a measurement."""
    MEASURED = auto()
    ESTIMATED = auto()
    HEURISTIC = auto()
    INFERRED = auto()
    UNKNOWN = auto()


class EnergyTier(Enum):
    """Energy hotspot classification."""
    HOT = auto()
    WARM = auto()
    COLD = auto()
    ZERO = auto()


@dataclass
class EFGNode:
    """A node in the energy flow graph, annotated with energy data."""
    id: int
    text: str
    ntype: str
    energy_j: float = 0.0
    exclusive_energy_j: float = 0.0
    self_ratio: float = 0.0
    rank_score: float = 0.0
    energy_pct: float = 0.0
    calls: int = 0
    energy_per_call_uj: float = 0.0
    estimated_iterations: Optional[float] = None
    tier: EnergyTier = EnergyTier.ZERO
    accuracy: Accuracy = Accuracy.UNKNOWN
    loop_depth: int = 0
    has_alloc: bool = False
    has_call: bool = False


@dataclass
class EFGEdge:
    """An edge in the energy flow graph with probability and energy data."""
    src: int
    dst: int
    label: str = ""
    probability: float = 1.0
    energy_j: float = 0.0
    accuracy: Accuracy = Accuracy.UNKNOWN
    is_hot: bool = False


@dataclass
class EnergyFlowGraph:
    """Complete energy flow graph for a single function/method."""
    function: str
    file: str
    total_energy_j: float
    exclusive_energy_j: float
    calls: int
    verdict: str
    accuracy: Accuracy = Accuracy.MEASURED
    nodes: dict[int, EFGNode] = field(default_factory=dict)
    edges: list[EFGEdge] = field(default_factory=list)
    hot_path: list[int] = field(default_factory=list)

    def hot_nodes(self) -> list[EFGNode]:
        """Return nodes classified as HOT energy hotspots."""
        return [n for n in self.nodes.values() if n.tier == EnergyTier.HOT]
