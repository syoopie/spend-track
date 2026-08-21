"""Shared API error-response construction.

Every error body follows the same {"code": ..., "message": ...} envelope.
Before this module existed, that envelope was hand-rolled independently in
most routers, and "not found" (_not_found()) was defined byte-identically
in both rules.py and contacts.py - centralizing it here means the shape
only has one place to change.
"""

from fastapi import HTTPException


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def not_found_error(entity: str, code: str) -> HTTPException:
    return api_error(404, code, f"No {entity} with that id.")
