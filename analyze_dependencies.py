#!/usr/bin/env python3
"""
Circular dependency analysis script for the Open Paper Trading MCP project.
"""

import ast
import sys
from pathlib import Path
from typing import Set, Dict, List, Tuple
from collections import defaultdict


class ImportAnalyzer(ast.NodeVisitor):
    """AST visitor to extract import information from Python files."""

    def __init__(self) -> None:
        self.imports: List[str] = []
        self.from_imports: List[Tuple[str, str]] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            for alias in node.names:
                self.from_imports.append((node.module, alias.name))


def analyze_file(file_path: Path) -> Tuple[List[str], List[Tuple[str, str]]]:
    """Analyze a Python file and extract its imports."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content)
        analyzer = ImportAnalyzer()
        analyzer.visit(tree)

        return analyzer.imports, analyzer.from_imports
    except (SyntaxError, UnicodeDecodeError, Exception) as e:
        print(f"Error analyzing {file_path}: {e}")
        return [], []


def normalize_module_name(module_name: str, current_package: str) -> str:
    """Normalize module names to project-relative paths."""
    if module_name.startswith("app."):
        return module_name
    elif module_name.startswith("."):
        # Relative import
        if current_package:
            if module_name.startswith(".."):
                # Parent package
                parent_parts = current_package.split(".")[:-1]
                relative_parts = (
                    module_name[2:].split(".") if len(module_name) > 2 else []
                )
                return (
                    ".".join(parent_parts + relative_parts)
                    if parent_parts or relative_parts
                    else current_package
                )
            else:
                # Same package
                relative_part = module_name[1:] if len(module_name) > 1 else ""
                return (
                    f"{current_package}.{relative_part}"
                    if relative_part
                    else current_package
                )
    return module_name


def get_package_name(file_path: Path, app_root: Path) -> str:
    """Get the package name for a file relative to the app root."""
    try:
        relative_path = file_path.relative_to(app_root)
        if relative_path.name == "__init__.py":
            relative_path = relative_path.parent
        else:
            relative_path = relative_path.with_suffix("")

        return str(relative_path).replace("/", ".").replace("\\", ".")
    except ValueError:
        return ""


def find_cycles(graph: Dict[str, Set[str]]) -> List[List[str]]:
    """Find cycles in a directed graph using DFS."""
    cycles = []
    visited = set()
    rec_stack = set()
    path: List[str] = []

    def dfs(node: str) -> bool:
        if node in rec_stack:
            # Found cycle
            cycle_start = path.index(node)
            cycle = path[cycle_start:] + [node]
            cycles.append(cycle)
            return True

        if node in visited:
            return False

        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in graph.get(node, set()):
            if dfs(neighbor):
                return True

        rec_stack.remove(node)
        path.pop()
        return False

    for node in graph:
        if node not in visited:
            dfs(node)

    return cycles


def analyze_project_dependencies() -> bool:
    """Analyze the entire project for circular dependencies."""
    app_root = Path("app")
    if not app_root.exists():
        print(
            "Error: 'app' directory not found. Run this script from the project root."
        )
        return False

    # Find all Python files
    python_files = []
    for file_path in app_root.rglob("*.py"):
        if "__pycache__" not in str(file_path):
            python_files.append(file_path)

    print(f"Analyzing {len(python_files)} Python files...")

    # Build dependency graph
    dependencies: Dict[str, Set[str]] = defaultdict(set)
    file_to_module: Dict[Path, str] = {}
    module_to_file: Dict[str, Path] = {}

    # First pass: map files to modules
    for file_path in python_files:
        package_name = get_package_name(file_path, Path("."))
        file_to_module[file_path] = package_name
        module_to_file[package_name] = file_path

    # Second pass: analyze imports
    for file_path in python_files:
        current_module = file_to_module[file_path]
        current_package = (
            ".".join(current_module.split(".")[:-1]) if "." in current_module else ""
        )

        imports, from_imports = analyze_file(file_path)

        # Process direct imports
        for imp in imports:
            normalized = normalize_module_name(imp, current_package)
            if normalized.startswith("app."):
                dependencies[current_module].add(normalized)

        # Process from imports
        for module, name in from_imports:
            normalized = normalize_module_name(module, current_package)
            if normalized.startswith("app."):
                dependencies[current_module].add(normalized)

    print("\nDependency Analysis Results:")
    print(f"{'=' * 50}")

    # Find cycles
    cycles = find_cycles(dependencies)

    if cycles:
        print(f"\n🚨 CIRCULAR DEPENDENCIES FOUND: {len(cycles)} cycle(s)")
        print(f"{'=' * 50}")

        for i, cycle in enumerate(cycles, 1):
            print(f"\nCycle {i}:")
            for j, module in enumerate(cycle[:-1]):
                print(f"  {module}")
                if j < len(cycle) - 2:
                    print("    ↓ imports")
            print(f"    ↑ imports back to {cycle[0]}")

            # Show actual files involved
            print("\n  Files involved:")
            for module in cycle[:-1]:  # Remove duplicate last element
                f_path: Path | None = module_to_file.get(module)
                print(f"    {module} → {f_path if f_path else 'Unknown'}")
    else:
        print("\n✅ NO CIRCULAR DEPENDENCIES FOUND")

    # Show dependency statistics
    print("\nDependency Statistics:")
    print(f"{'=' * 30}")
    print(f"Total modules analyzed: {len(file_to_module)}")
    print(
        f"Modules with dependencies: {len([m for m in dependencies if dependencies[m]])}"
    )

    # Show most connected modules
    dependency_counts = [(len(deps), module) for module, deps in dependencies.items()]
    dependency_counts.sort(reverse=True)

    print("\nMost connected modules (top 10):")
    for count, module in dependency_counts[:10]:
        if count > 0:
            print(f"  {module}: {count} dependencies")

    # Show modules that are imported by many others
    imported_by = defaultdict(set)
    for module, deps in dependencies.items():
        for dep in deps:
            imported_by[dep].add(module)

    import_counts = [
        (len(importers), module) for module, importers in imported_by.items()
    ]
    import_counts.sort(reverse=True)

    print("\nMost imported modules (top 10):")
    for count, module in import_counts[:10]:
        if count > 0:
            print(f"  {module}: imported by {count} modules")

    # Detailed dependency mapping
    print("\nDetailed Dependency Map:")
    print(f"{'=' * 30}")

    for module in sorted(dependencies.keys()):
        deps = dependencies[module]
        if deps:
            print(f"\n{module}:")
            for dep in sorted(deps):
                print(f"  → {dep}")

    return len(cycles) == 0


if __name__ == "__main__":
    print("Open Paper Trading MCP - Circular Dependency Analysis")
    print("=" * 60)

    success = analyze_project_dependencies()
    sys.exit(0 if success else 1)
