"""
Utility functions for generating and validating account IDs.
"""
import random
import re
import string
from typing import Any


def generate_account_id() -> str:
    """
    Generate a 10-character alphanumeric account ID.
    
    Format: [A-Z0-9]{10}
    Examples: "A1B2C3D4E5", "XYZ1234567"
    
    Returns:
        str: A 10-character alphanumeric string
    """
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choices(characters, k=10))


def is_valid_account_id(account_id: Any) -> bool:
    """
    Validate that an account ID meets the required format.
    
    Requirements:
    - Exactly 10 characters
    - Only uppercase letters (A-Z) and digits (0-9)
    
    Args:
        account_id: The account ID to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not isinstance(account_id, str):
        return False
    
    if len(account_id) != 10:
        return False
    
    # Check if all characters are alphanumeric (A-Z, 0-9)
    pattern = re.compile(r'^[A-Z0-9]{10}$')
    return bool(pattern.match(account_id))


def validate_account_id(account_id: str) -> str:
    """
    Validate and return an account ID, raising ValueError if invalid.
    
    Args:
        account_id: The account ID to validate
        
    Returns:
        str: The validated account ID
        
    Raises:
        ValueError: If account ID format is invalid
    """
    if not is_valid_account_id(account_id):
        raise ValueError(
            f"Invalid account ID format: '{account_id}'. "
            "Account ID must be exactly 10 alphanumeric characters (A-Z, 0-9)."
        )
    return account_id


def validate_optional_account_id(account_id: str | None) -> str | None:
    """
    Validate optional account ID parameter.
    
    Args:
        account_id: Optional account ID to validate
        
    Returns:
        The validated account ID or None if not provided
        
    Raises:
        ValueError: If the account ID is provided but invalid
    """
    if account_id is None:
        return None
    return validate_account_id(account_id)