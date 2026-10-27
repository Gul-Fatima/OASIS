"""Control Flow Graph (CFG) data structures.

Extracted from SMART-Dal/codegreen (MPL-2.0).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class NType(Enum):
    """Node types in a control flow graph."""
    ENTRY = auto()
    EXIT = auto()
    STMT = auto()
    COND = auto()
    LOOP = auto()
    BREAK = auto()
    CONTINUE = auto()
    RETURN = auto()
    SWITCH = auto()
    CASE = auto()


@dataclass
class CNode:
    """A single node in the control flow graph."""
    id: int
    ntype: NType
    text: str = ""
    succs: set[int] = field(default_factory=set)
    preds: set[int] = field(default_factory=set)
    edge_labels: dict[int, str] = field(default_factory=dict)
    defs: list[str] = field(default_factory=list)
    uses: list[str] = field(default_factory=list)
    ast_type: str = ""
    has_alloc: bool = False
    calls: list[str] = field(default_factory=list)

    def add_succ(self, to: int, label: str | None = None):
        self.succs.add(to)
        if label:
            self.edge_labels[to] = label

    def add_pred(self, fr: int):
        self.preds.add(fr)


@dataclass
class CFG:
    """Control Flow Graph: nodes, entry point, and exit nodes."""
    nodes: dict[int, CNode] = field(default_factory=dict)
    entry: int = -1
    exits: list[int] = field(default_factory=list)
    _nxt: int = 0

    def node(self, ntype: NType, text: str = "", ast_type: str = "") -> int:
        """Create a new node and return its ID."""
        nid = self._nxt
        self._nxt += 1
        self.nodes[nid] = CNode(id=nid, ntype=ntype, text=text, ast_type=ast_type)
        return nid

    def edge(self, a: int, b: int, label: str | None = None):
        """Add a directed edge from node a to node b."""
        if a in self.nodes and b in self.nodes:
            self.nodes[a].add_succ(b, label)
            self.nodes[b].add_pred(a)
