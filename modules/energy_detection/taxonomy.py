"""Energy Smells Taxonomy

A two-level taxonomy of software energy smells: 12 primary categories
and 65 root-cause subcategories.

Source: ``third_party/energy-smells/taxonomy.md`` (SMART-Dal/Energy-Smells,
CC-BY-4.0; Rajput et al. "A Comprehensive Taxonomy of Software Energy
Smells"). This module is the canonical in-code mirror of that document:
categories, subcategory ids, names and ordering must match it, and
``okeb.json`` is aligned onto this file by ``okeb_align.py``. A previous
revision replaced C11/C12 with a different taxonomy and an extra C12.S5,
which made 7 OKEB rules unlabelled; do not reintroduce that drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Subcategory:
    id: str
    name: str
    parent_id: str
    description: str


@dataclass(frozen=True)
class Category:
    id: str
    name: str
    description: str
    subcategories: tuple[Subcategory, ...] = field(default_factory=tuple)


# ── C1: Redundant Computation ──────────────────────────────────────

_C1 = Category(
    id="C1",
    name="Redundant Computation",
    description=(
        "Energy waste from executing work that does not contribute to the "
        "program's required output or that leaves program state unchanged."
    ),
    subcategories=(
        Subcategory("C1.S1", "Dead Code", "C1",
                     "Code that executes but whose results are never consumed, "
                     "or code that can never be reached."),
        Subcategory("C1.S2", "Redundant Assignment", "C1",
                     "Statements that leave program state effectively unchanged."),
        Subcategory("C1.S3", "Redundant Control Flow", "C1",
                     "Control flow constructs that do not alter program execution."),
        Subcategory("C1.S4", "Repeated Computation", "C1",
                     "Performing the same calculation multiple times within the "
                     "same scope when the underlying data has not changed."),
        Subcategory("C1.S5", "Resultless Computation", "C1",
                     "Code that executes but produces no output that any "
                     "subsequent code uses."),
        Subcategory("C1.S6", "Unnecessary Initialization", "C1",
                     "Performs setup or allocation on execution paths where the "
                     "result may never be used or is immediately overwritten."),
        Subcategory("C1.S7", "Unnecessary Variable", "C1",
                     "Defining intermediate variables whose overhead exceeds "
                     "their utility for readability or reuse."),
        Subcategory("C1.S8", "Excessive Runtime-Management Calls", "C1",
                     "Invoking expensive runtime housekeeping (gc.collect(), "
                     "logging) more often than needed."),
    ),
)

# ── C2: Unnecessary Call Overhead ──────────────────────────────────

_C2 = Category(
    id="C2",
    name="Unnecessary Call Overhead",
    description=(
        "Energy waste from extra layers of function calls, method delegation, "
        "or dynamic dispatch that add overhead without proportional benefit."
    ),
    subcategories=(
        Subcategory("C2.S1", "Unnecessary Method Delegation", "C2",
                     "Delegates a simple operation through extra layers of calls "
                     "or wrappers."),
        Subcategory("C2.S2", "Missing Static Declaration", "C2",
                     "Uses instance methods when the operation does not depend "
                     "on any instance state."),
        Subcategory("C2.S3", "Excessive Modularization in Hot Path", "C2",
                     "Splits a performance-critical flow into too many tiny "
                     "functions whose combined call overhead exceeds useful work."),
    ),
)

# ── C3: Inefficient Iteration Patterns ─────────────────────────────

_C3 = Category(
    id="C3",
    name="Inefficient Iteration Patterns",
    description=(
        "Energy waste from loops that perform more per-iteration work than "
        "necessary, iterate more times than required, or use suboptimal constructs."
    ),
    subcategories=(
        Subcategory("C3.S1", "Inefficient Iteration Construct", "C3",
                     "Uses an iteration form with avoidable overhead."),
        Subcategory("C3.S2", "Recomputing Loop-Invariant Values", "C3",
                     "Recomputes values inside the loop that remain constant "
                     "across all iterations."),
        Subcategory("C3.S3", "Inefficient Per-Iteration Setup", "C3",
                     "Creates expensive objects or allocates resources inside "
                     "a loop body on every iteration."),
        Subcategory("C3.S4", "Inefficient Nested Iteration", "C3",
                     "Uses nested loops where an equivalent approach would "
                     "reduce overall complexity."),
        Subcategory("C3.S5", "Missing Loop Early Exit", "C3",
                     "Continues iterating after the required result has already "
                     "been determined."),
        Subcategory("C3.S6", "Unfiltered Bulk Iteration", "C3",
                     "Processes all items when only a subset is needed."),
        Subcategory("C3.S7", "Inefficient Array Mutation in Loop", "C3",
                     "Modifies the same collection being iterated, causing "
                     "iteration anomalies or redundant re-indexing."),
    ),
)

# ── C4: Inefficient Control Flow ───────────────────────────────────

_C4 = Category(
    id="C4",
    name="Inefficient Control Flow",
    description=(
        "Energy waste from branching, conditions, or dispatch logic that "
        "performs unnecessary checks or uses suboptimal evaluation order."
    ),
    subcategories=(
        Subcategory("C4.S1", "Poor Short-Circuit Ordering", "C4",
                     "Orders AND/OR operands so expensive checks run before "
                     "cheap ones."),
        Subcategory("C4.S2", "Redundant Conditional Evaluation", "C4",
                     "Evaluates conditions that are always true or always false."),
        Subcategory("C4.S3", "Inefficient Conditional Nesting", "C4",
                     "Uses deeply nested conditionals that prevent early returns."),
        Subcategory("C4.S4", "Missing Else-If", "C4",
                     "Uses multiple independent if statements when branches "
                     "are mutually exclusive."),
        Subcategory("C4.S5", "Expensive Comparison", "C4",
                     "Uses higher-cost type introspection when simpler "
                     "comparisons exist."),
        Subcategory("C4.S6", "Expensive Exception Control Flow", "C4",
                     "Uses try/except as the primary mechanism for selecting "
                     "between expected outcomes in high-frequency paths."),
        Subcategory("C4.S7", "Missing Edge-Case Guards", "C4",
                     "Fails to check trivial inputs that would allow skipping "
                     "expensive processing."),
        Subcategory("C4.S8", "Non-Idiomatic Condition", "C4",
                     "Uses non-idiomatic conditional patterns that miss "
                     "runtime optimizations."),
    ),
)

# ── C5: Suboptimal Data Structures ─────────────────────────────────

_C5 = Category(
    id="C5",
    name="Suboptimal Data Structures",
    description=(
        "Energy waste from choosing data structures that do not match the "
        "workload's access pattern or size requirements."
    ),
    subcategories=(
        Subcategory("C5.S1", "Inefficient Data Structure Choice", "C5",
                     "Uses a data structure with worse complexity for the "
                     "dominant operation."),
        Subcategory("C5.S2", "Missing Helper Type", "C5",
                     "Fails to introduce an auxiliary data structure that would "
                     "turn repeated scans into cheap lookups."),
        Subcategory("C5.S3", "Over-Provisioned Data Type", "C5",
                     "Chooses a heavier type than the data requires."),
        Subcategory("C5.S4", "Unnecessary Representation Change", "C5",
                     "Converts between representations without a net "
                     "efficiency gain."),
    ),
)

# ── C6: Unnecessary Memory Usage ───────────────────────────────────

_C6 = Category(
    id="C6",
    name="Unnecessary Memory Usage",
    description=(
        "Patterns that allocate, copy, retain, or leak memory beyond what "
        "the workload requires."
    ),
    subcategories=(
        Subcategory("C6.S1", "Unnecessary Object", "C6",
                     "Creates more objects than necessary, increasing GC pressure."),
        Subcategory("C6.S2", "Unnecessary Copying", "C6",
                     "Copies data when a reference or in-place operation "
                     "would suffice."),
        Subcategory("C6.S3", "Unnecessary Data Materialization", "C6",
                     "Materializes intermediate data structures fully in memory "
                     "when lazy evaluation would suffice."),
        Subcategory("C6.S4", "Oversized Data Retaining", "C6",
                     "Keeps entire data structures when smaller representations "
                     "would suffice."),
        Subcategory("C6.S5", "Over-Allocation", "C6",
                     "Allocates larger buffers than typical inputs require."),
        Subcategory("C6.S6", "Leaked Resource Handles", "C6",
                     "Fails to release external resources promptly after use."),
        Subcategory("C6.S7", "Leaking Mutable Default Arguments", "C6",
                     "Uses a mutable object as a default parameter value, "
                     "causing accumulated state across calls."),
    ),
)

# ── C7: Suboptimal Algorithmic ─────────────────────────────────────

_C7 = Category(
    id="C7",
    name="Suboptimal Algorithmic",
    description=(
        "Energy waste from choosing an algorithm or decomposition that "
        "explores more of the problem space than necessary."
    ),
    subcategories=(
        Subcategory("C7.S1", "Suboptimal Algorithm Choice", "C7",
                     "Uses an algorithm with known worse complexity."),
        Subcategory("C7.S2", "Inefficient Problem Decomposition", "C7",
                     "Decomposes a problem in a way that leads to redundant "
                     "subproblem computation."),
        Subcategory("C7.S3", "Avoidable Recursive Implementation", "C7",
                     "Uses recursion where an iterative solution is straightforward."),
        Subcategory("C7.S4", "Inefficient Operation Ordering", "C7",
                     "Executes the more expensive operation before cheaper "
                     "filtering or pruning."),
        Subcategory("C7.S5", "Unsimplified Operation", "C7",
                     "Performs a heavy operation on inputs that could be "
                     "algebraically simplified first."),
    ),
)

# ── C8: Missing Reuse ──────────────────────────────────────────────

_C8 = Category(
    id="C8",
    name="Missing Reuse",
    description=(
        "Energy waste from failing to store and reuse results of expensive "
        "computations or lookups."
    ),
    subcategories=(
        Subcategory("C8.S1", "Missing Memoization Cache", "C8",
                     "Recomputes deterministic expensive function results "
                     "instead of caching."),
        Subcategory("C8.S2", "Missing Derived-Value Reuse", "C8",
                     "Recreates expensive derived artifacts on every use."),
        Subcategory("C8.S3", "Missing Local Lookup Caching", "C8",
                     "Repeatedly performs chained attribute access in hot code "
                     "instead of caching in a local variable."),
        Subcategory("C8.S4", "Redundant Data Fetching", "C8",
                     "Repeatedly retrieves the same data from an external source."),
    ),
)

# ── C9: Inefficient External Data Access ───────────────────────────

_C9 = Category(
    id="C9",
    name="Inefficient External Data Access",
    description=(
        "Energy waste from inefficient interaction with databases, file "
        "systems, network services, and APIs."
    ),
    subcategories=(
        Subcategory("C9.S1", "Fragmented I/O Calls", "C9",
                     "Performs many small I/O operations individually "
                     "instead of batching."),
        Subcategory("C9.S2", "Oversized Data Retrieval", "C9",
                     "Fetches more data than the application consumes."),
        Subcategory("C9.S3", "Inefficient Retrieval Paths", "C9",
                     "Requires multiple dependent retrieval steps when a "
                     "single combined query would suffice."),
        Subcategory("C9.S4", "Expensive Query Pattern", "C9",
                     "Uses query structures that are inherently costly."),
    ),
)

# ── C10: Underused Language Primitives ─────────────────────────────

_C10 = Category(
    id="C10",
    name="Underused Language Primitives",
    description=(
        "Energy waste from not using available optimized language features "
        "or standard library functions."
    ),
    subcategories=(
        Subcategory("C10.S1", "Skipping Optimized Built-ins", "C10",
                     "Manually implements functionality available as optimized "
                     "built-ins."),
        Subcategory("C10.S2", "Inefficient Built-in Choice", "C10",
                     "Chooses a slower built-in when a faster alternative exists."),
        Subcategory("C10.S3", "Missing Bulk Primitive Usage", "C10",
                     "Uses per-element operations when batch/vectorized "
                     "primitives exist."),
        Subcategory("C10.S4", "Inefficient String Concatenation", "C10",
                     "Builds strings via repeated concatenation instead of "
                     "mutable builders."),
        Subcategory("C10.S5", "Inefficient Scope Lookup", "C10",
                     "Places variables in scopes with unnecessary lookup overhead."),
        Subcategory("C10.S6", "Expensive Operator Overloads", "C10",
                     "Uses operators on custom types that trigger expensive "
                     "overloaded methods."),
    ),
)

# ── C11: Inefficient Concurrency Management ────────────────────────

_C11 = Category(
    id="C11",
    name="Inefficient Concurrency Management",
    description=(
        "Energy waste from thread/task misuse, synchronization overhead, "
        "contention, or failure to exploit available parallelism."
    ),
    subcategories=(
        Subcategory("C11.S1", "Excessive Lock Contention", "C11",
                     "Uses heavyweight synchronization too frequently, on "
                     "overly broad critical sections, or with coarse-grained "
                     "locks that serialize work that could proceed in parallel."),
        Subcategory("C11.S2", "Forced Serial Bottleneck", "C11",
                     "Architecture forces execution through a single shared "
                     "resource, global lock, or pipeline stage that all "
                     "threads must pass through, negating parallelism."),
        Subcategory("C11.S3", "Leaked Background Threads", "C11",
                     "Starts threads, processes, or async tasks that are never "
                     "stopped, joined, or allowed to terminate cleanly."),
        Subcategory("C11.S4", "Blocking The Main Thread", "C11",
                     "Performs long-running CPU or I/O work on the main event "
                     "loop or UI thread, causing the application to freeze "
                     "while wasting energy on idle synchronization waits."),
        Subcategory("C11.S5", "Missed Parallelism Opportunities", "C11",
                     "Executes independent work items serially even though "
                     "they could run concurrently, underutilizing available "
                     "CPU cores or I/O bandwidth."),
    ),
)

# ── C12: Poor Hardware Locality Usage ──────────────────────────────

_C12 = Category(
    id="C12",
    name="Poor Hardware Locality Usage",
    description=(
        "Energy waste driven by CPU and memory hierarchy behavior such as "
        "cache misses, branch misprediction, and suboptimal memory access "
        "patterns."
    ),
    subcategories=(
        Subcategory("C12.S1", "Inefficient Large-Stride Traversal", "C12",
                     "Traverses arrays or multi-dimensional data with a stride "
                     "pattern that causes frequent cache misses, defeating "
                     "spatial locality and hardware prefetching."),
        Subcategory("C12.S2", "Sparse Element Access", "C12",
                     "Touches a small, scattered subset of elements inside a "
                     "large contiguous data structure, wasting most of each "
                     "cache line loaded."),
        Subcategory("C12.S3", "Unpredictable Branches", "C12",
                     "Uses highly data-dependent branching in tight loops that "
                     "defeats branch prediction, causing pipeline stalls and "
                     "wasted speculative execution energy."),
        Subcategory("C12.S4", "Inefficient Array Declaration Order", "C12",
                     "Declares or allocates hot arrays after rarely used ones, "
                     "placing frequently accessed data at less cache-friendly "
                     "offsets."),
    ),
)


# ── Public registry ─────────────────────────────────────────────────

ENERGY_SMELL_CATEGORIES: tuple[Category, ...] = (
    _C1, _C2, _C3, _C4, _C5, _C6, _C7, _C8, _C9, _C10, _C11, _C12,
)

_ALL_SUBCATS: dict[str, Subcategory] = {}
for _cat in ENERGY_SMELL_CATEGORIES:
    for _sub in _cat.subcategories:
        _ALL_SUBCATS[_sub.id] = _sub


def get_category(category_id: str) -> Category | None:
    """Look up a category by ID (e.g. 'C1')."""
    for cat in ENERGY_SMELL_CATEGORIES:
        if cat.id == category_id:
            return cat
    return None


def get_subcategories(category_id: str) -> list[Subcategory]:
    """Return all subcategories under a given category ID."""
    cat = get_category(category_id)
    return list(cat.subcategories) if cat else []


def get_subcategory(subcategory_id: str) -> Subcategory | None:
    """Look up a subcategory by ID (e.g. 'C1.S3')."""
    return _ALL_SUBCATS.get(subcategory_id)


def format_categories_for_prompt() -> str:
    """Format all categories as a string for LLM prompts."""
    lines = []
    for cat in ENERGY_SMELL_CATEGORIES:
        lines.append(f"- {cat.id} — {cat.name}: {cat.description}")
    return "\n".join(lines)


def format_subcategories_for_prompt(category_ids: list[str]) -> str:
    """Format subcategories for the given category IDs."""
    lines = []
    for cid in category_ids:
        cat = get_category(cid)
        if cat:
            for sub in cat.subcategories:
                lines.append(f"- {sub.id} — {sub.name}: {sub.description}")
    return "\n".join(lines)
