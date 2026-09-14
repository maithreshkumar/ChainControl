import uuid


class CorrelationIdMiddleware:
    header = "HTTP_X_CORRELATION_ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        value = request.META.get(self.header, "")
        try:
            request.correlation_id = str(uuid.UUID(value)) if value else str(uuid.uuid4())
        except ValueError:
            request.correlation_id = str(uuid.uuid4())
        response = self.get_response(request)
        response["X-Correlation-ID"] = request.correlation_id
        return response

