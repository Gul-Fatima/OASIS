"""CLI entry point for the Code Understanding module.

Usage:
    cd modules
    python code_understanding/main.py
    # Then enter a path to a .py file
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running from modules/ directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from code_understanding.parser import parse_code


def main() -> None:
    path_input = input("Enter path to a Python file: ").strip()
    path = Path(path_input)

    if not path.exists():
        print(f"Error: file not found: {path_input}")
        sys.exit(1)

    if not path.is_file():
        print(f"Error: not a file: {path_input}")
        sys.exit(1)

    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print(f"Error: could not read file as UTF-8: {path_input}")
        sys.exit(1)

    try:
        state = parse_code(source, path=str(path), language="python")
    except ValueError as exc:
        print(f"Parse error: {exc}")
        sys.exit(1)

    print()
    print("=" * 60)
    print("           CODE UNDERSTANDING RESULTS")
    print("=" * 60)

    print(f"  File       : {state.path}")
    print(f"  Language   : {state.language}")
    print(f"  Functions  : {len(state.functions)}")
    print(f"  Classes    : {len(state.classes)}")
    print(f"  Loops      : {len(state.loops)}")
    print(f"  Conditionals: {state.conditionals}")
    print(f"  Calls      : {len(state.function_calls)}")
    print(f"  IO Ops     : {len(state.io_operations)}")
    print(f"  Allocs     : {state.allocations}")
    print(f"  Deps       : {state.dependencies}")
    print(f"  Complexity : {state.complexity}")
    print("=" * 60)

    # Detailed info
    if state.functions:
        print()
        print("Functions:")
        for f in state.functions:
            cx = f"  complexity={f.complexity}" if f.complexity is not None else ""
            print(f"  - {f.name}(args={f.arguments}) lines {f.start_line}-{f.end_line}{cx}")
            if f.decorators:
                print(f"    decorators: {f.decorators}")

    if state.classes:
        print()
        print("Classes:")
        for c in state.classes:
            print(f"  - {c.name} lines {c.start_line}-{c.end_line} ({len(c.methods)} methods)")
            for m in c.methods:
                print(f"      {m.name}({m.arguments}) lines {m.start_line}-{m.end_line}")

    if state.loops:
        print()
        print("Loops:")
        for loop in state.loops:
            print(f"  - {loop.kind} at line {loop.line}")

    if state.function_calls:
        print()
        print("Function calls:")
        for c in state.function_calls:
            print(f"  - {c.name}() at line {c.line} ({c.argument_count} args)")

    if state.io_operations:
        print()
        print("I/O operations:")
        for io in state.io_operations:
            print(f"  - {io}")

    if state.data_structures:
        print()
        print("Data structures:", state.data_structures)

    # JSON export
    print()
    json_path = path.with_suffix(".code_state.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(state.to_dict(), f, indent=2)
    print(f"Full JSON written to: {json_path}")


if __name__ == "__main__":
    main()
