"""
Response helper functions for maintaining Flask-compatible response format.
"""
from typing import Any, Dict, Optional
from fastapi.responses import JSONResponse


def success_response(**data) -> JSONResponse:
    """
    Return a success response in the same format as Flask:
    {"success": True, ...data}
    """
    return JSONResponse(content={"success": True, **data})


def error_response(
    message: str,
    status_code: int = 400,
    **extra
) -> JSONResponse:
    """
    Return an error response in the same format as Flask:
    {"success": False, "message": "error message", ...extra}
    """
    content = {"success": False, "message": message, **extra}
    return JSONResponse(content=content, status_code=status_code)
