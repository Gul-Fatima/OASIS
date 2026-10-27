"""EFG output formats: compact text, DOT, Mermaid, JSON.

Extracted from SMART-Dal/codegreen (MPL-2.0).
"""

from typing import Optional

from .efg_heuristics import DEFAULT_CONFIG, EFGConfig, NTYPE_SHAPES
from .efg_types import EnergyFlowGraph, EnergyTier


def dot_escape(text: str) -> str:
    return text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ').replace('\r', '')


def truncate_label(text: str, max_len: int) -> str:
    """Truncate at a syntax boundary."""
    if len(text) <= max_len:
        return text
    for sep in (';', ',', ')', '(', ' '):
        idx = text.rfind(sep, 0, max_len)
        if idx > max_len // 2:
            return text[:idx + 1] + "..."
    return text[:max_len] + "..."


def efg_to_text(efg: EnergyFlowGraph, config: Optional[EFGConfig] = None) -> str:
    """Compact text representation suitable for LLM prompts."""
    cfg = config or DEFAULT_CONFIG
    lines = [f"EFG: {efg.function} ({efg.exclusive_energy_j:.1f}J exclusive, "
             f"{efg.total_energy_j:.1f}J total, {efg.calls} calls, {efg.verdict})"]
    if efg.hot_path:
        lines.append(f"  Hot path: {' -> '.join(str(n) for n in efg.hot_path)}")
    for node in sorted(efg.nodes.values(), key=lambda n: n.rank_score, reverse=True):
        if node.rank_score < cfg.min_rank_display or node.ntype in ('ENTRY', 'EXIT'):
            continue
        indent = "  " + "  " * node.loop_depth
        tag = "CALL" if node.has_call else "ALLOC" if node.has_alloc else node.ntype
        iters = f" ~{node.estimated_iterations:.0f}x" if node.estimated_iterations else ""
        lines.append(f"{indent}{node.tier.name} [{node.accuracy.name}] "
                     f"rank={node.rank_score:.0f}{iters} {tag}: {node.text}")
    branches = [(e.src, e.label, e.probability) for e in efg.edges if e.label]
    if branches:
        lines.append("  Branches:")
        for src, label, prob in branches:
            src_text = efg.nodes[src].text[:30] if src in efg.nodes else str(src)
            lines.append(f"    {src_text} --{label}--> p={prob:.2f}")
    return "\n".join(lines)


def efg_to_dot(efg: EnergyFlowGraph, config: Optional[EFGConfig] = None) -> str:
    """DOT graph format for visualization."""
    cfg = config or DEFAULT_CONFIG
    lines = [
        f'digraph "{dot_escape(efg.function)}" {{',
        '  rankdir=TB;',
        f'  fontname="Courier"; fontsize=12;',
        f'  node [fontname="Courier" fontsize=10 margin="0.1,0.05"];',
        f'  edge [fontname="Courier" fontsize=9];',
        f'  label="{dot_escape(efg.function)}\\n'
        f'{efg.exclusive_energy_j:.1f}J | {efg.calls} calls | {efg.verdict}";',
        '  labelloc=t;',
    ]
    for node in efg.nodes.values():
        color = cfg.tier_colors.get(node.tier, '#F0F0F0') if hasattr(cfg, 'tier_colors') else TIER_COLORS.get(node.tier, '#F0F0F0')
        fc = cfg.tier_font_colors.get(node.tier, 'black') if hasattr(cfg, 'tier_font_colors') else 'black'
        shape = NTYPE_SHAPES.get(node.ntype, 'ellipse')
        short = truncate_label(dot_escape(node.text), cfg.dot_label_max)
        label = f"{short}\\nrank={node.rank_score:.0f} [{node.accuracy.name}]"
        lines.append(f'  {node.id} [label="{label}" shape={shape} style=filled '
                     f'fillcolor="{color}" fontcolor={fc}];')
    for edge in efg.edges:
        attrs = []
        if edge.label:
            attrs.append(f'label="{edge.label} p={edge.probability:.2f}"')
        if edge.energy_j > 0:
            attrs.append(f'taillabel="{edge.energy_j:.1f}J"')
        if edge.is_hot:
            attrs.append('color="#CC0000" penwidth=3.0')
        attr_str = f' [{", ".join(attrs)}]' if attrs else ''
        lines.append(f'  {edge.src} -> {edge.dst}{attr_str};')
    lines.append('}')
    return '\n'.join(lines)


def efg_to_mermaid(efg: EnergyFlowGraph, config: Optional[EFGConfig] = None) -> str:
    """Mermaid diagram format."""
    cfg = config or DEFAULT_CONFIG
    tier_class = {EnergyTier.HOT: 'hot', EnergyTier.WARM: 'warm',
                  EnergyTier.COLD: 'cold', EnergyTier.ZERO: 'zero'}
    lines = ['graph TD']
    for node in efg.nodes.values():
        cls = tier_class.get(node.tier, 'zero')
        safe = node.text.replace('"', "'").replace('\n', ' ').replace('<', '&lt;').replace('>', '&gt;')
        short = truncate_label(safe, cfg.dot_label_max)
        label = f"{short}<br/>rank={node.rank_score:.0f}"
        lines.append(f'    N{node.id}["{label}"]:::{cls}')
    for edge in efg.edges:
        label = f"|{edge.label} p={edge.probability:.2f}| " if edge.label else ""
        lines.append(f'    N{edge.src} -->{label} N{edge.dst}')
    for tier_name, css_class in tier_class.items():
        color = TIER_COLORS.get(tier_name, '#F0F0F0')
        fc = TIER_FONT_COLORS.get(tier_name, 'black')
        lines.append(f'    classDef {css_class} fill:{color},color:{fc}')
    return '\n'.join(lines)


def efg_to_json(efg: EnergyFlowGraph) -> dict:
    """JSON-serializable dict."""
    return {
        "function": efg.function, "file": efg.file,
        "total_energy_j": efg.total_energy_j,
        "exclusive_energy_j": efg.exclusive_energy_j,
        "calls": efg.calls, "verdict": efg.verdict,
        "accuracy": efg.accuracy.name,
        "nodes": [{"id": n.id, "text": n.text, "ntype": n.ntype,
                   "rank_score": n.rank_score, "energy_j": n.energy_j,
                   "tier": n.tier.name, "accuracy": n.accuracy.name,
                   "has_alloc": n.has_alloc, "has_call": n.has_call,
                   "loop_depth": n.loop_depth}
                  for n in efg.nodes.values()],
        "edges": [{"src": e.src, "dst": e.dst, "label": e.label,
                   "probability": e.probability, "energy_j": e.energy_j,
                   "accuracy": e.accuracy.name, "is_hot": e.is_hot}
                  for e in efg.edges],
        "hot_path": efg.hot_path,
    }
