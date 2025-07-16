#!/usr/bin/env python3
"""
Simple import checker that focuses on missing classes and functions
in files that actually exist, avoiding environment dependency issues.
"""

import ast
import sys
from pathlib import Path
from typing import Set, Dict, List


class MissingClassChecker:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.errors: List[str] = []
        
    def check_file_imports(self, file_path: Path) -> None:
        """Check imports in a single file for missing classes/functions."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return
            
        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError:
            return
            
        relative_path = file_path.relative_to(self.project_root)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module
                if not module:
                    continue
                    
                # Only check local modules (app.*)
                if not module.startswith('app.'):
                    continue
                    
                # Convert module path to file path
                target_file = self.find_module_file(module)
                if not target_file:
                    continue
                    
                # Check if imported names exist in target file
                for alias in node.names:
                    if alias.name == '*':
                        continue
                        
                    if not self.name_exists_in_file(target_file, alias.name):
                        self.errors.append(
                            f"{relative_path}:{node.lineno}: "
                            f"'{alias.name}' not found in module '{module}'"
                        )
    
    def find_module_file(self, module: str) -> Path | None:
        """Find the file for a given module path."""
        parts = module.split('.')
        if parts[0] != 'app':
            return None
            
        # Start from app directory
        current_path = self.project_root / 'app'
        
        # Navigate through module parts (skip 'app')
        for part in parts[1:]:
            current_path = current_path / part
            
        # Check for package directory with __init__.py
        if current_path.is_dir() and (current_path / '__init__.py').exists():
            return current_path / '__init__.py'
            
        # Check for .py file
        py_file = current_path.with_suffix('.py')
        if py_file.exists():
            return py_file
            
        return None
    
    def name_exists_in_file(self, file_path: Path, name: str) -> bool:
        """Check if a name is defined in a file using AST parsing."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                # Check for class definitions
                if isinstance(node, ast.ClassDef) and node.name == name:
                    return True
                    
                # Check for function definitions
                if isinstance(node, ast.FunctionDef) and node.name == name:
                    return True
                    
                # Check for async function definitions
                if isinstance(node, ast.AsyncFunctionDef) and node.name == name:
                    return True
                    
                # Check for assignments
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == name:
                            return True
                            
                # Check for imports that bring in the name
                if isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        imported_name = alias.asname or alias.name
                        if imported_name == name:
                            return True
                            
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported_name = alias.asname or alias.name
                        if imported_name == name:
                            return True
                            
        except Exception:
            pass
            
        return False
    
    def check_all_files(self) -> int:
        """Check all Python files in the project."""
        print(f"Checking for missing classes/functions in {self.project_root}...")
        
        for py_file in self.project_root.rglob("*.py"):
            # Skip virtual environments and cache directories
            if any(part in str(py_file) for part in [".venv", "__pycache__", "venv", ".git"]):
                continue
                
            self.check_file_imports(py_file)
            
        # Print results
        if self.errors:
            print(f"\nFound {len(self.errors)} missing class/function imports:")
            for error in sorted(self.errors):
                print(f"❌ {error}")
        else:
            print("✅ All local class/function imports found!")
            
        return len(self.errors)


def main() -> None:
    project_root = Path(__file__).parent.parent
    checker = MissingClassChecker(project_root)
    error_count = checker.check_all_files()
    sys.exit(1 if error_count > 0 else 0)


if __name__ == "__main__":
    main()