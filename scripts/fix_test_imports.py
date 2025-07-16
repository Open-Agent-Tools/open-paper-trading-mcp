#!/usr/bin/env python3
"""
Systematic script to fix common test import and validation issues after schema refactoring.
"""

import re
from pathlib import Path


def fix_order_constructor_patterns(content: str) -> str:
    """Fix Order constructor patterns that use old syntax."""

    # Pattern 1: Order(asset=..., quantity=negative, ...)
    # Should become: OrderLeg(asset=..., quantity=positive, order_type=SELL/STC)

    # Pattern to match Order with asset field and negative quantity
    pattern1 = r"Order\(asset=([^,]+),\s*quantity=(-\d+),\s*order_type=([^,)]+)([^)]*)\)\.to_leg\(\)"

    def replace_order_asset_negative(match: re.Match[str]) -> str:
        asset = match.group(1)
        quantity = abs(int(match.group(2)))  # Make positive
        order_type = match.group(3)
        rest = match.group(4)
        return f"OrderLeg(asset={asset}, quantity={quantity}, order_type={order_type}{rest})"

    content = re.sub(pattern1, replace_order_asset_negative, content)

    # Pattern 2: Order(asset=..., quantity=positive, ...)
    # Should become: OrderLeg(asset=..., quantity=..., ...)
    pattern2 = r"Order\(asset=([^,]+),\s*quantity=(\d+),\s*order_type=([^,)]+)([^)]*)\)\.to_leg\(\)"

    def replace_order_asset_positive(match: re.Match[str]) -> str:
        asset = match.group(1)
        quantity = match.group(2)
        order_type = match.group(3)
        rest = match.group(4)
        return f"OrderLeg(asset={asset}, quantity={quantity}, order_type={order_type}{rest})"

    content = re.sub(pattern2, replace_order_asset_positive, content)

    return content


def fix_option_constructor_patterns(content: str) -> str:
    """Fix Option constructor patterns."""

    # Pattern: Call(underlying_symbol="SYMBOL", ...)
    # Should become: Call(underlying_asset=Stock(symbol="SYMBOL"), ...)
    pattern = r'(Call|Put)\(underlying_symbol="([^"]+)"'

    def replace_option_constructor(match: re.Match[str]) -> str:
        option_type = match.group(1)
        symbol = match.group(2)
        return f'{option_type}(underlying_asset=Stock(symbol="{symbol}")'

    content = re.sub(pattern, replace_option_constructor, content)

    # Pattern: Option("SYMBOL") -> Option.from_symbol("SYMBOL")
    pattern2 = r'Option\("([^"]+)"\)'
    content = re.sub(pattern2, r'Option.from_symbol("\1")', content)

    return content


def fix_import_statements(content: str) -> str:
    """Fix import statements to include missing imports."""

    # If we see OrderLeg usage but no import, add it
    if "OrderLeg(" in content and "from app.schemas.orders import" in content:
        # Check if OrderLeg is already imported
        import_pattern = r"from app\.schemas\.orders import ([^)\n]+)"
        match = re.search(import_pattern, content)
        if match:
            imports = match.group(1)
            if "OrderLeg" not in imports:
                # Add OrderLeg to the import
                new_imports = imports.rstrip() + ", OrderLeg"
                content = re.sub(
                    import_pattern,
                    f"from app.schemas.orders import {new_imports}",
                    content,
                )

    return content


def process_test_file(file_path: Path) -> bool:
    """Process a single test file and return True if changes were made."""

    try:
        with open(file_path, "r") as f:
            original_content = f.read()

        content = original_content

        # Apply fixes
        content = fix_order_constructor_patterns(content)
        content = fix_option_constructor_patterns(content)
        content = fix_import_statements(content)

        # Write back if changed
        if content != original_content:
            with open(file_path, "w") as f:
                f.write(content)
            print(f"Fixed: {file_path}")
            return True

        return False

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main() -> None:
    """Main function to process all test files."""

    test_dir = Path("tests")

    if not test_dir.exists():
        print("Tests directory not found!")
        return

    test_files = list(test_dir.rglob("test_*.py"))

    print(f"Found {len(test_files)} test files")

    fixed_count = 0
    for test_file in test_files:
        if process_test_file(test_file):
            fixed_count += 1

    print(f"Fixed {fixed_count} files")


if __name__ == "__main__":
    main()
