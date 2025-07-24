"""
Standardized response utilities for MCP tools.

All MCP tools should return dict[str, Any] with a standardized format
containing a 'result' field with 'status' and 'data'/'error' fields.
"""

from typing import Any


def success_response(data: Any) -> dict[str, Any]:
    """
    Create a standardized success response.

    Args:
        data: The successful response data

    Returns:
        dict[str, Any]: Standardized success response
    """
    return {"result": {"status": "success", "data": data}}


def error_response(error_message: str) -> dict[str, Any]:
    """
    Create a standardized error response.

    Args:
        error_message: The error message

    Returns:
        dict[str, Any]: Standardized error response
    """
    return {"result": {"status": "error", "error": error_message}}


def handle_tool_exception(func_name: str, exception: Exception) -> dict[str, Any]:
    """
    Handle exceptions in MCP tools with standardized error response.

    Args:
        func_name: Name of the function where the exception occurred
        exception: The caught exception

    Returns:
        dict[str, Any]: Standardized error response
    """
    error_msg = f"Error in {func_name}: {exception!s}"
    return error_response(error_msg)
