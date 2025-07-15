#!/usr/bin/env python3
"""
Create a visual dependency analysis report for the Open Paper Trading MCP project.
"""

import ast
from pathlib import Path
from typing import Set, Dict, List, Tuple
from collections import defaultdict


class ImportAnalyzer(ast.NodeVisitor):
    """AST visitor to extract import information from Python files."""
    
    def __init__(self):
        self.imports = []
        self.from_imports = []
    
    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append(alias.name)
    
    def visit_ImportFrom(self, node):
        if node.module:
            for alias in node.names:
                self.from_imports.append((node.module, alias.name))


def analyze_file(file_path: Path) -> Tuple[List[str], List[Tuple[str, str]]]:
    """Analyze a Python file and extract its imports."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
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
    if module_name.startswith('app.'):
        return module_name
    elif module_name.startswith('.'):
        # Relative import
        if current_package:
            if module_name.startswith('..'):
                # Parent package
                parent_parts = current_package.split('.')[:-1]
                relative_parts = module_name[2:].split('.') if len(module_name) > 2 else []
                return '.'.join(parent_parts + relative_parts) if parent_parts or relative_parts else current_package
            else:
                # Same package
                relative_part = module_name[1:] if len(module_name) > 1 else ''
                return f"{current_package}.{relative_part}" if relative_part else current_package
    return module_name


def get_package_name(file_path: Path, app_root: Path) -> str:
    """Get the package name for a file relative to the app root."""
    try:
        relative_path = file_path.relative_to(app_root)
        if relative_path.name == '__init__.py':
            relative_path = relative_path.parent
        else:
            relative_path = relative_path.with_suffix('')
        
        return str(relative_path).replace('/', '.').replace('\\', '.')
    except ValueError:
        return ''


def analyze_by_layer():
    """Analyze dependencies by architectural layer."""
    app_root = Path('app')
    if not app_root.exists():
        print("Error: 'app' directory not found.")
        return
    
    # Find all Python files
    python_files = []
    for file_path in app_root.rglob('*.py'):
        if '__pycache__' not in str(file_path):
            python_files.append(file_path)
    
    # Define architectural layers
    layers = {
        'models': [],
        'adapters': [],
        'services': [],
        'api': [],
        'mcp': [],
        'storage': [],
        'core': []
    }
    
    # Build dependency graph
    dependencies = defaultdict(set)
    file_to_module = {}
    
    # First pass: categorize modules by layer
    for file_path in python_files:
        package_name = get_package_name(file_path, Path('.'))
        file_to_module[file_path] = package_name
        
        # Categorize by layer
        if package_name.startswith('app.models.'):
            layers['models'].append(package_name)
        elif package_name.startswith('app.adapters.'):
            layers['adapters'].append(package_name)
        elif package_name.startswith('app.services.'):
            layers['services'].append(package_name)
        elif package_name.startswith('app.api.'):
            layers['api'].append(package_name)
        elif package_name.startswith('app.mcp.'):
            layers['mcp'].append(package_name)
        elif package_name.startswith('app.storage.'):
            layers['storage'].append(package_name)
        elif package_name.startswith('app.core.'):
            layers['core'].append(package_name)
    
    # Second pass: analyze imports
    for file_path in python_files:
        current_module = file_to_module[file_path]
        current_package = '.'.join(current_module.split('.')[:-1]) if '.' in current_module else ''
        
        imports, from_imports = analyze_file(file_path)
        
        # Process direct imports
        for imp in imports:
            normalized = normalize_module_name(imp, current_package)
            if normalized.startswith('app.'):
                dependencies[current_module].add(normalized)
        
        # Process from imports
        for module, name in from_imports:
            normalized = normalize_module_name(module, current_package)
            if normalized.startswith('app.'):
                dependencies[current_module].add(normalized)
    
    # Analyze cross-layer dependencies
    layer_dependencies = defaultdict(lambda: defaultdict(int))
    
    for module, deps in dependencies.items():
        source_layer = get_layer(module)
        for dep in deps:
            target_layer = get_layer(dep)
            if source_layer and target_layer:
                layer_dependencies[source_layer][target_layer] += 1
    
    print("Open Paper Trading MCP - Architectural Dependency Analysis")
    print("=" * 65)
    
    # Show layer composition
    print("\nLayer Composition:")
    print("-" * 20)
    for layer, modules in layers.items():
        print(f"{layer.upper()}: {len(modules)} modules")
        for module in sorted(modules):
            print(f"  • {module}")
        print()
    
    # Show cross-layer dependencies
    print("Cross-Layer Dependencies:")
    print("-" * 30)
    for source_layer, targets in layer_dependencies.items():
        print(f"\n{source_layer.upper()} depends on:")
        for target_layer, count in sorted(targets.items()):
            print(f"  → {target_layer}: {count} dependencies")
    
    # Check for architectural violations
    print("\nArchitectural Analysis:")
    print("-" * 25)
    
    violations = []
    
    # API should not depend on MCP
    if layer_dependencies['api']['mcp'] > 0:
        violations.append("❌ API layer depends on MCP layer")
    
    # MCP should not depend on API
    if layer_dependencies['mcp']['api'] > 0:
        violations.append("❌ MCP layer depends on API layer")
    
    # Models should have minimal dependencies
    models_deps = sum(layer_dependencies['models'].values())
    if models_deps > 5:  # Arbitrary threshold
        violations.append(f"⚠️  Models layer has many dependencies ({models_deps})")
    
    # Services should not depend on API/MCP
    if layer_dependencies['services']['api'] > 0:
        violations.append("❌ Services layer depends on API layer")
    if layer_dependencies['services']['mcp'] > 0:
        violations.append("❌ Services layer depends on MCP layer")
    
    if violations:
        print("Potential architectural violations found:")
        for violation in violations:
            print(f"  {violation}")
    else:
        print("✅ No major architectural violations detected")
    
    # Show dependency flow
    print("\nRecommended Dependency Flow:")
    print("-" * 32)
    print("API/MCP → Services → Adapters → Models")
    print("       ↘     ↓            ↓")
    print("        Core ← Storage ← Models")
    
    # Analyze specific problematic patterns
    print("\nSpecific Dependency Analysis:")
    print("-" * 35)
    
    # Check trading_service dependencies
    trading_service_deps = dependencies.get('app.services.trading_service', set())
    print(f"trading_service dependencies ({len(trading_service_deps)}):")
    for dep in sorted(trading_service_deps):
        print(f"  → {dep}")
    
    # Check MCP tools dependencies
    mcp_tools_deps = dependencies.get('app.mcp.tools', set())
    print(f"\nmcp.tools dependencies ({len(mcp_tools_deps)}):")
    for dep in sorted(mcp_tools_deps):
        print(f"  → {dep}")
    
    # Show most central modules
    imported_by = defaultdict(set)
    for module, deps in dependencies.items():
        for dep in deps:
            imported_by[dep].add(module)
    
    print(f"\nMost Central Modules (high fan-in):")
    import_counts = [(len(importers), module) for module, importers in imported_by.items()]
    import_counts.sort(reverse=True)
    
    for count, module in import_counts[:5]:
        if count > 0:
            print(f"  {module}: imported by {count} modules")
            for importer in sorted(imported_by[module]):
                print(f"    ← {importer}")


def get_layer(module_name: str) -> str:
    """Get the architectural layer for a module."""
    if module_name.startswith('app.models.'):
        return 'models'
    elif module_name.startswith('app.adapters.'):
        return 'adapters'
    elif module_name.startswith('app.services.'):
        return 'services'
    elif module_name.startswith('app.api.'):
        return 'api'
    elif module_name.startswith('app.mcp.'):
        return 'mcp'
    elif module_name.startswith('app.storage.'):
        return 'storage'
    elif module_name.startswith('app.core.'):
        return 'core'
    return ''


if __name__ == "__main__":
    analyze_by_layer()