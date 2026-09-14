from rest_framework.views import exception_handler as drf_exception_handler


class DomainError(Exception):
    def __init__(self, code: str, message: str, *, status_code: int = 400, details=None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


def exception_handler(exc, context):
    request = context.get("request")
    correlation_id = getattr(request, "correlation_id", None)
    if isinstance(exc, DomainError):
        from rest_framework.response import Response

        return Response(
            {"error": {"code": exc.code, "message": exc.message, "details": exc.details}, "correlation_id": correlation_id},
            status=exc.status_code,
        )
    response = drf_exception_handler(exc, context)
    if response is not None:
        response.data = {
            "error": {"code": "REQUEST_INVALID", "message": "The request could not be processed.", "details": response.data},
            "correlation_id": correlation_id,
        }
    return response

