#!/usr/bin/env python3
"""
Comprehensive import validator for the Open Paper Trading MCP project.
Checks all Python files for import issues including:
- Missing modules/files
- Incorrect import paths
- Non-existent classes/functions
- Schema vs model confusion
"""

import ast
import sys
from pathlib import Path
from typing import Dict, List, Any
import importlib.util
import re


class ImportChecker:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.app_root = project_root / "app"
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.checked_files = 0
        self.total_imports = 0

        # Add project root to sys.path for import resolution
        sys.path.insert(0, str(project_root))

    def check_all_files(self) -> None:
        """Check all Python files in the project."""
        print(f"Scanning Python files in {self.project_root}...")

        for py_file in self.project_root.rglob("*.py"):
            # Skip virtual environments and cache directories
            if any(
                part in str(py_file)
                for part in [".venv", "__pycache__", "venv", ".git"]
            ):
                continue

            self.check_file(py_file)

        self.print_report()

    def check_file(self, file_path: Path) -> None:
        """Check all imports in a single file."""
        self.checked_files += 1
        relative_path = file_path.relative_to(self.project_root)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            self.errors.append(f"{relative_path}: Failed to read file - {e}")
            return

        # Parse AST to find imports
        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError as e:
            self.errors.append(f"{relative_path}: Syntax error - {e}")
            return

        # Extract imports
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(
                        {
                            "module": alias.name,
                            "name": alias.asname or alias.name,
                            "line": node.lineno,
                            "type": "import",
                        }
                    )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                level = node.level  # Number of dots in relative import

                # Handle relative imports
                if level > 0:
                    # Convert relative to absolute import path
                    file_package = self._get_package_path(file_path)
                    if file_package:
                        parts = file_package.split(".")
                        if level <= len(parts):
                            parent_parts = parts[:-level]
                            if module:
                                module = ".".join(parent_parts + [module])
                            else:
                                module = ".".join(parent_parts)

                for alias in node.names:
                    imports.append(
                        {
                            "module": module,
                            "name": alias.name,
                            "asname": alias.asname,
                            "line": node.lineno,
                            "type": "from",
                            "level": level,
                        }
                    )

        # Check each import
        for imp in imports:
            self.total_imports += 1
            self.check_import(imp, file_path, relative_path)

    def _get_package_path(self, file_path: Path) -> str:
        """Get the package path for a file."""
        try:
            relative = file_path.relative_to(self.project_root)
            parts = list(relative.parts[:-1])  # Exclude the file name
            if relative.stem != "__init__":
                parts.append(relative.stem)
            return ".".join(parts)
        except ValueError:
            return ""

    def check_import(
        self, imp: Dict[str, Any], file_path: Path, relative_path: Path
    ) -> None:
        """Check a single import statement."""
        line_info = f"{relative_path}:{imp['line']}"

        if imp["type"] == "import":
            # Check 'import module' style
            module_name = imp["module"]
            if not self._module_exists(module_name):
                self.errors.append(
                    f"{line_info}: Import error - module '{module_name}' not found"
                )
            else:
                # Check for schema vs model confusion
                if "schema" in module_name and "model" in str(file_path):
                    self.warnings.append(
                        f"{line_info}: Possible schema/model confusion - importing schema in model file"
                    )
                elif "model" in module_name and "schema" in str(file_path):
                    self.warnings.append(
                        f"{line_info}: Possible model/schema confusion - importing model in schema file"
                    )

        else:  # from ... import ...
            module_name = imp["module"]
            import_name = imp["name"]

            # Check if module exists
            if not module_name:
                # This might be a relative import with only dots
                return

            if not self._module_exists(module_name):
                self.errors.append(
                    f"{line_info}: Import error - module '{module_name}' not found"
                )
                return

            # Check if the imported name exists in the module
            if import_name != "*":
                if not self._name_exists_in_module(module_name, import_name):
                    self.errors.append(
                        f"{line_info}: Import error - '{import_name}' not found in module '{module_name}'"
                    )

            # Check for common schema/model confusion patterns
            self._check_schema_model_confusion(module_name, import_name, line_info)

    def _module_exists(self, module_name: str) -> bool:
        """Check if a module exists and can be imported."""
        if not module_name:
            return True

        # Check if it's a built-in or installed module
        try:
            spec = importlib.util.find_spec(module_name)
            return spec is not None
        except (ImportError, ModuleNotFoundError, ValueError):
            pass

        # Check if it's a local module (convert dot notation to path)
        parts = module_name.split(".")

        # Try from project root
        module_path = self.project_root
        for part in parts:
            module_path = module_path / part

        # Check for package directory
        if module_path.is_dir() and (module_path / "__init__.py").exists():
            return True

        # Check for module file
        if module_path.with_suffix(".py").exists():
            return True

        return False

    def _name_exists_in_module(self, module_name: str, name: str) -> bool:
        """Check if a name exists in a module."""
        try:
            # Try to import the module
            module = importlib.import_module(module_name)
            return hasattr(module, name)
        except Exception:
            # If we can't import, try to parse the source file
            parts = module_name.split(".")
            module_path = self.project_root

            for part in parts:
                module_path = module_path / part

            # Check in __init__.py if it's a package
            if module_path.is_dir():
                init_file = module_path / "__init__.py"
                if init_file.exists():
                    return self._name_in_file(init_file, name)

            # Check in .py file
            py_file = module_path.with_suffix(".py")
            if py_file.exists():
                return self._name_in_file(py_file, name)

            return False

    def _name_in_file(self, file_path: Path, name: str) -> bool:
        """Check if a name is defined in a file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Check for direct definitions
            patterns = [
                rf"^class {name}\b",
                rf"^def {name}\b",
                rf"^{name} =",
                rf"^from .* import .*\b{name}\b",
                rf"^from .* import .* as {name}\b",
            ]

            for pattern in patterns:
                if re.search(pattern, content, re.MULTILINE):
                    return True

            # Check __all__ export
            if f'"{name}"' in content or f"'{name}'" in content:
                return True

        except Exception:
            pass

        return False

    def _check_schema_model_confusion(
        self, module_name: str, import_name: str, line_info: str
    ) -> None:
        """Check for common schema/model confusion patterns."""
        # Pattern 1: Importing from schemas when it should be models
        if "schemas" in module_name and import_name in [
            "Order",
            "Position",
            "Account",
            "Transaction",
        ]:
            if "database" not in module_name:  # Database models are OK
                self.warnings.append(
                    f"{line_info}: Possible confusion - importing '{import_name}' from schemas (should it be from models?)"
                )

        # Pattern 2: Importing Response models from wrong location
        if import_name.endswith("Response") and "schemas" not in module_name:
            self.warnings.append(
                f"{line_info}: Response model '{import_name}' should typically be imported from schemas"
            )

        # Pattern 3: SQLAlchemy models imported from wrong location
        if "models.database" not in module_name and import_name in [
            "Base",
            "Column",
            "Integer",
            "String",
        ]:
            if "sqlalchemy" not in module_name:
                self.warnings.append(
                    f"{line_info}: Database model '{import_name}' should be imported from models.database or sqlalchemy"
                )

    def print_report(self) -> None:
        """Print the final report."""
        print(f"\n{'=' * 80}")
        print("Import Validation Report")
        print(f"{'=' * 80}")
        print(f"Files checked: {self.checked_files}")
        print(f"Total imports: {self.total_imports}")
        print(f"Errors found: {len(self.errors)}")
        print(f"Warnings found: {len(self.warnings)}")

        if self.errors:
            print(f"\n{'=' * 80}")
            print("ERRORS:")
            print(f"{'=' * 80}")
            for error in sorted(self.errors):
                print(f"❌ {error}")

        if self.warnings:
            print(f"\n{'=' * 80}")
            print("WARNINGS:")
            print(f"{'=' * 80}")
            for warning in sorted(self.warnings):
                print(f"⚠️  {warning}")

        if not self.errors and not self.warnings:
            print("\n✅ All imports are valid!")

        print(f"\n{'=' * 80}")

        # Return exit code based on errors
        # return 1 if self.errors else 0


def main() -> None:
    """Main entry point."""
    project_root = Path(__file__).parent.parent
    checker = ImportChecker(project_root)
    checker.check_all_files()
    sys.exit(1 if checker.errors else 0)


if __name__ == "__main__":
    main()
