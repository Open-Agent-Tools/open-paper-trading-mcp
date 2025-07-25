#!/usr/bin/env python3
"""
Dependency analysis script for the Open Paper Trading MCP project.
"""

import ast
import sys
from pathlib import Path

import toml

# Known standard library modules in Python 3.10
STD_LIB_MODULES = {
    "abc",
    "aifc",
    "argparse",
    "array",
    "ast",
    "asyncio",
    "atexit",
    "audioop",
    "base64",
    "bdb",
    "binascii",
    "bisect",
    "builtins",
    "bz2",
    "calendar",
    "cgi",
    "cgitb",
    "chunk",
    "cmath",
    "cmd",
    "code",
    "codecs",
    "codeop",
    "collections",
    "colorsys",
    "compileall",
    "concurrent",
    "configparser",
    "contextlib",
    "contextvars",
    "copy",
    "copyreg",
    "csv",
    "ctypes",
    "curses",
    "dataclasses",
    "datetime",
    "dbm",
    "decimal",
    "difflib",
    "dis",
    "distutils",
    "doctest",
    "email",
    "encodings",
    "enum",
    "errno",
    "faulthandler",
    "fcntl",
    "filecmp",
    "fileinput",
    "fnmatch",
    "fractions",
    "ftplib",
    "functools",
    "gc",
    "getopt",
    "getpass",
    "gettext",
    "glob",
    "grp",
    "gzip",
    "hashlib",
    "heapq",
    "hmac",
    "html",
    "http",
    "imaplib",
    "imghdr",
    "imp",
    "importlib",
    "inspect",
    "io",
    "ipaddress",
    "itertools",
    "json",
    "keyword",
    "lib2to3",
    "linecache",
    "locale",
    "logging",
    "lzma",
    "mailbox",
    "mailcap",
    "marshal",
    "math",
    "mimetypes",
    "mmap",
    "modulefinder",
    "multiprocessing",
    "netrc",
    "nntplib",
    "numbers",
    "operator",
    "optparse",
    "os",
    "ossaudiodev",
    "parser",
    "pathlib",
    "pdb",
    "pickle",
    "pickletools",
    "pipes",
    "pkgutil",
    "platform",
    "plistlib",
    "poplib",
    "posix",
    "pprint",
    "profile",
    "pstats",
    "pty",
    "pwd",
    "py_compile",
    "pyclbr",
    "pydoc",
    "queue",
    "quopri",
    "random",
    "re",
    "readline",
    "reprlib",
    "resource",
    "rlcompleter",
    "runpy",
    "sched",
    "secrets",
    "select",
    "selectors",
    "shelve",
    "shlex",
    "shutil",
    "signal",
    "site",
    "smtpd",
    "smtplib",
    "sndhdr",
    "socket",
    "socketserver",
    "sqlite3",
    "ssl",
    "stat",
    "statistics",
    "string",
    "stringprep",
    "struct",
    "subprocess",
    "sunau",
    "symbol",
    "symtable",
    "sys",
    "sysconfig",
    "syslog",
    "tabnanny",
    "tarfile",
    "telnetlib",
    "tempfile",
    "termios",
    "textwrap",
    "threading",
    "time",
    "timeit",
    "tkinter",
    "token",
    "tokenize",
    "trace",
    "traceback",
    "tracemalloc",
    "tty",
    "turtle",
    "turtledemo",
    "types",
    "typing",
    "unicodedata",
    "unittest",
    "urllib",
    "uu",
    "uuid",
    "venv",
    "warnings",
    "wave",
    "weakref",
    "webbrowser",
    "wsgiref",
    "xdrlib",
    "xml",
    "xmlrpc",
    "zipapp",
    "zipfile",
    "zipimport",
    "zlib",
}


class ImportVisitor(ast.NodeVisitor):
    def __init__(self):
        self.imports = set()

    def visit_Import(self, node):  # noqa: N802
        for alias in node.names:
            self.imports.add(alias.name.split(".")[0])
        self.generic_visit(node)

    def visit_ImportFrom(self, node):  # noqa: N802
        if node.module and node.level == 0:  # only check absolute imports
            self.imports.add(node.module.split(".")[0])
        self.generic_visit(node)


def get_imports_from_file(file_path: Path) -> set:
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
        tree = ast.parse(content)
        visitor = ImportVisitor()
        visitor.visit(tree)
        return visitor.imports
    except Exception as e:
        print(f"Could not parse {file_path}: {e}", file=sys.stderr)
        return set()


def get_local_modules(project_root: Path) -> set:
    local_modules = set()
    for path in project_root.iterdir():
        if path.is_dir() and (path / "__init__.py").exists():
            local_modules.add(path.name)
    return local_modules


def analyze_dependencies():
    project_root = Path(__file__).parent.parent
    pyproject_path = project_root / "pyproject.toml"

    # 1. Get declared dependencies from pyproject.toml
    try:
        pyproject_data = toml.load(pyproject_path)
        # Adjusting for [project] table for dependencies
        dependencies = {
            pkg.split("[")[0].split(">")[0].split("<")[0].split("=")[0]
            for pkg in pyproject_data.get("project", {}).get("dependencies", [])
        }
        dev_dependencies = {
            pkg.split("[")[0].split(">")[0].split("<")[0].split("=")[0]
            for pkg in pyproject_data.get("project", {})
            .get("optional-dependencies", {})
            .get("dev", [])
        }
        all_declared_deps = dependencies.union(dev_dependencies)
        all_declared_deps.discard("python")
    except Exception as e:
        print(f"Error reading {pyproject_path}: {e}", file=sys.stderr)
        return

    # 2. Find all python files and gather imports
    all_imports = set()
    for py_file in project_root.rglob("*.py"):
        if ".venv" in py_file.parts:
            continue
        all_imports.update(get_imports_from_file(py_file))

    # 3. Identify third-party imports
    local_modules = get_local_modules(project_root)
    third_party_imports = set()
    for imp in all_imports:
        if imp not in STD_LIB_MODULES and imp not in local_modules:
            third_party_imports.add(imp)

    # Normalize names (e.g., robin_stocks -> robin-stocks)
    normalized_third_party = {imp.replace("_", "-") for imp in third_party_imports}

    # Special mappings for packages where import name differs from package name
    mapping = {
        "dotenv": "python-dotenv",
        "google": "google-api-python-client",
        "jose": "python-jose",
        "passlib": "passlib",
        "robin_stocks": "robin-stocks",
    }

    mapped_third_party = set()
    for imp in normalized_third_party:
        mapped_third_party.add(mapping.get(imp, imp))

    # 4. Compare and report
    missing_in_pyproject = mapped_third_party - all_declared_deps
    unused_in_code = all_declared_deps - mapped_third_party

    print("--- Dependency Analysis Report ---")

    if missing_in_pyproject:
        print("\n[ERROR] Found imported modules not in pyproject.toml:")
        for dep in sorted(missing_in_pyproject):
            print(f"  - {dep}")
    else:
        print("\n[OK] All imported third-party modules are declared in pyproject.toml.")

    if unused_in_code:
        print("\n[WARNING] Found dependencies in pyproject.toml that may not be used:")
        for dep in sorted(unused_in_code):
            print(f"  - {dep}")
    else:
        print("\n[OK] All declared dependencies appear to be used in the code.")

    print("\n--- End of Report ---")


if __name__ == "__main__":
    analyze_dependencies()
