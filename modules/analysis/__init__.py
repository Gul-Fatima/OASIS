"""Analysis Module

Control Flow Graph (CFG) and Energy Flow Graph (EFG) data structures
and construction logic.

Based on: SMART-Dal/codegreen (MPL-2.0)
"""

from .cfg_types import CFG, CNode, NType
from .efg_types import Accuracy, EFGNode, EFGEdge, EnergyFlowGraph, EnergyTier
from .efg_heuristics import EFGConfig, classify_edge_probability
from .efg_serialize import efg_to_text, efg_to_dot, efg_to_json
