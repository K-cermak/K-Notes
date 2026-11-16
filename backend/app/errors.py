from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErrorResponse(BaseModel):
    code: str
    message: str


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class NotFoundError(AppError):
    def __init__(self, message: str = "Not found") -> None:
        super().__init__(404, "not_found", message)


_STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "too_large",
    429: "too_many_requests",
}


def _error(status_code: int, code: str, message: str, headers: Any = None) -> JSONResponse:
    body = ErrorResponse(code=code, message=message).model_dump()
    return JSONResponse(body, status_code=status_code, headers=headers)


async def _app_error(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    retry_after = getattr(exc, "retry_after", None)
    headers = {"Retry-After": str(retry_after)} if retry_after else None
    return _error(exc.status_code, exc.code, exc.message, headers)


async def _http_error(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = _STATUS_CODES.get(exc.status_code, "error")
    return _error(exc.status_code, code, str(exc.detail), getattr(exc, "headers", None))


async def _validation_error(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    errors: list[dict[str, Any]] = list(exc.errors())
    first = errors[0] if errors else {}
    location = ".".join(str(part) for part in first.get("loc", ()))
    message = f"{location}: {first.get('msg', 'invalid')}" if location else "Invalid request"
    return _error(422, "validation_error", message)


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Sign in to continue") -> None:
        super().__init__(401, "unauthorized", message)


class ForbiddenError(AppError):
    def __init__(self, code: str = "forbidden", message: str = "Not allowed") -> None:
        super().__init__(403, code, message)


class ConflictError(AppError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(409, code, message)


class InvalidInputError(AppError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(422, code, message)


class TooManyRequestsError(AppError):
    def __init__(self, retry_after: int) -> None:
        super().__init__(429, "too_many_requests", f"Too many attempts. Try again in {retry_after} s.")
        self.retry_after = retry_after
