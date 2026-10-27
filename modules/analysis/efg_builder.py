"""EFG construction: annotate CFG nodes with energy data.

Extracted from SMART-Dal/codegreen (MPL-2.0).

Design principles:
- Method-level energy is MEASURED (from checkpoints).
- Statement-level energy is a RANKING HEURISTIC, not Joule values.
- Edge weights represent EXECUTION FREQUENCY, not energy cost.
- Ball & Larus (1993) heuristics for branch probabilities.
"""

from __future__ import annotations

from typing import Optional

from .efg_heuristics import (
    DEFAULT_CONFIG, EFGConfig, HOT_EDGE_FRACTION,
    classify_edge_probability, INSTRUMENTATION_MARKERS,
)
from .efg_paths import longest_path_dag
from .efg_types import (
    Accuracy, EFGEdge, EFGNode, EnergyFlowGraph, EnergyTier,
)


def build_efg(
    cfg_nodes: list,
    cfg_edges: list,
    fn_name: str,
    fn_file: str,
    cg_entry: dict,
    cg_functions: Optional[dict] = None,
    config: Optional[EFGConfig] = None,
) -> EnergyFlowGraph:
    """Build an Energy Flow Graph from CFG nodes/edges + energy data."""
    cfg = config or DEFAULT_CONFIG
    rw = cfg.rank_weights
    fn_inclusive = cg_entry.get("energy_j", 0)
    fn_exclusive = cg_entry.get("exclusive_energy_j", fn_inclusive)
    fn_calls = cg_entry.get("calls", 1) or 1
    verdict = cg_entry.get("verdict", "")

    node_ids = {getattr(n, 'id', i) for i, n in enumerate(cfg_nodes)}
    computed_depths = _compute_loop_depths(cfg_edges, node_ids)

    efg_nodes: dict[int, EFGNode] = {}
    for node in cfg_nodes:
        ntype = getattr(node, 'ntype', None)
        ntype_name = ntype.name if hasattr(ntype, 'name') else str(ntype)
        text = getattr(node, 'text', '')
        loop_depth = getattr(node, 'loop_depth', 0) or computed_depths.get(node.id, 0)
        has_alloc = 'new ' in text or 'alloc' in text.lower()
        is_instrumentation = any(m in text for m in cfg.instrumentation_markers)
        has_call = ('(' in text and ntype_name not in ('ENTRY', 'EXIT', 'LOOP', 'COND')
                    and not is_instrumentation)

        callee_calls = _get_callee_calls(text, cg_functions, fn_name) if has_call else None
        if callee_calls is not None and callee_calls > 0:
            rank = float(callee_calls)
            acc = Accuracy.ESTIMATED
        elif has_alloc:
            rank = float(rw.get("ALLOC", 5))
            acc = Accuracy.HEURISTIC
        elif has_call:
            rank = float(rw.get("CALL", 3))
            acc = Accuracy.HEURISTIC
        else:
            rank = float(rw.get(ntype_name, 1))
            acc = Accuracy.HEURISTIC

        if ntype_name in ('ENTRY', 'EXIT') or is_instrumentation:
            acc = Accuracy.UNKNOWN
            rank = 0.0

        efg_nodes[node.id] = EFGNode(
            id=node.id, text=text[:cfg.node_text_max], ntype=ntype_name,
            rank_score=rank, calls=fn_calls,
            accuracy=acc, loop_depth=loop_depth,
            has_alloc=has_alloc, has_call=has_call,
        )

    _assign_tiers(efg_nodes, cfg.tier_hot, cfg.tier_warm)
    efg_edges = _build_edges(cfg_edges, efg_nodes)
    _mark_hot_edges(efg_edges, efg_nodes, cfg.hot_edge_fraction)
    hot_path = longest_path_dag(efg_nodes, efg_edges)

    return EnergyFlowGraph(
        function=fn_name, file=fn_file,
        total_energy_j=fn_inclusive, exclusive_energy_j=fn_exclusive,
        calls=fn_calls, verdict=verdict,
        nodes=efg_nodes, edges=efg_edges, hot_path=hot_path,
    )


# ── Internal helpers ────────────────────────────────────────────────

def _extract_callee_name(text: str) -> Optional[str]:
    idx = text.find('(')
    if idx < 0:
        return None
    prefix = text[:idx].strip()
    dot = prefix.rfind('.')
    eq = prefix.rfind('=')
    start = max(dot, eq, prefix.rfind(' ')) + 1
    name = prefix[start:].strip()
    return name if name else None


def _get_callee_calls(text: str, cg_functions: Optional[dict], fn_name: str) -> Optional[int]:
    callee = _extract_callee_name(text)
    if not callee or not cg_functions:
        return None
    cls_prefix = fn_name.rsplit('.', 1)[0] + '.' if '.' in fn_name else ''
    for key in [cls_prefix + callee, callee]:
        if key in cg_functions:
            return cg_functions[key].get("calls", 0)
    return None


def _compute_loop_depths(cfg_edges: list, node_ids: set) -> dict[int, int]:
    depths: dict[int, int] = {nid: 0 for nid in node_ids}
    loop_headers = set()
    for src, dst, label in cfg_edges:
        if label.lower() == "true" and src in node_ids:
            for s2, d2, _ in cfg_edges:
                if d2 == src and s2 != src and s2 in node_ids:
                    loop_headers.add(src)
                    break
    for lh in loop_headers:
        body = set()
        for src, dst, label in cfg_edges:
            if src == lh and label.lower() == "true":
                _collect_body(dst, lh, cfg_edges, body)
                body.add(dst)
        for nid in body:
            depths[nid] = depths.get(nid, 0) + 1
    return depths


def _collect_body(start: int, loop_id: int, cfg_edges: list, visited: set) -> None:
    worklist = [start]
    while worklist:
        node = worklist.pop()
        for src, dst, _ in cfg_edges:
            if src == node and dst != loop_id and dst not in visited:
                visited.add(dst)
                worklist.append(dst)


def _assign_tiers(nodes: dict[int, EFGNode], hot_t: float, warm_t: float) -> None:
    ranked = sorted([n for n in nodes.values() if n.rank_score > 0],
                    key=lambda n: n.rank_score, reverse=True)
    for i, node in enumerate(ranked):
        if i == 0:
            node.tier = EnergyTier.HOT
        elif len(ranked) > 1:
            pos = i / (len(ranked) - 1)
            node.tier = (EnergyTier.HOT if pos <= hot_t else
                         EnergyTier.WARM if pos <= warm_t else EnergyTier.COLD)
        else:
            node.tier = EnergyTier.HOT
    for node in nodes.values():
        if node.rank_score <= 0:
            node.tier = EnergyTier.ZERO


def _build_edges(cfg_edges: list, nodes: dict[int, EFGNode]) -> list[EFGEdge]:
    efg_edges = []
    for src, dst, label in cfg_edges:
        src_node = nodes.get(src)
        dst_node = nodes.get(dst)
        prob = classify_edge_probability(label, src_node, dst_node)
        acc = Accuracy.HEURISTIC if not label else Accuracy.MEASURED
        efg_edges.append(EFGEdge(src=src, dst=dst, label=label, probability=prob, accuracy=acc))
    return efg_edges


def _mark_hot_edges(edges: list[EFGEdge], nodes: dict[int, EFGNode],
                    fraction: int = HOT_EDGE_FRACTION) -> None:
    if not edges:
        return
    scores = sorted(
        [e.probability * nodes.get(e.src, EFGNode(0, "", "STMT")).rank_score for e in edges],
        reverse=True)
    threshold = scores[max(0, len(scores) // fraction)]
    for e in edges:
        score = e.probability * nodes.get(e.src, EFGNode(0, "", "STMT")).rank_score
        e.is_hot = score >= threshold and score > 0
