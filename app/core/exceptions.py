from fastapi import HTTPException
from typing import Any, Dict, Optional


class CustomException(HTTPException):
    def __init__(
        self,
        status_code: int,
        detail: Any = None,
        headers: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(status_code, detail, headers)


class ValidationError(CustomException):
    def __init__(self, detail: str = "Validation error"):
        super().__init__(status_code=422, detail=detail)


class NotFoundError(CustomException):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=404, detail=detail)


class UnauthorizedError(CustomException):
    def __init__(self, detail: str = "Unauthorized"):
        super().__init__(status_code=401, detail=detail)


class ForbiddenError(CustomException):
    def __init__(self, detail: str = "Forbidden"):
        super().__init__(status_code=403, detail=detail)


class ConflictError(CustomException):
    def __init__(self, detail: str = "Conflict"):
        super().__init__(status_code=409, detail=detail)