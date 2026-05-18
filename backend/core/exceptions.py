"""Custom DRF exception handler for the FusionPBX-Django project.

All API errors are normalised to a consistent JSON envelope::

    {
        "status": 400,
        "error": "Bad Request",
        "message": "Human-readable summary.",
        "errors": {
            "field_name": ["Validation message."],
            "non_field_errors": ["Cross-field message."]
        }
    }

The ``errors`` key is only present when there are field-level validation
details (i.e. for ``ValidationError`` exceptions).  For all other error
types the envelope contains only ``status``, ``error``, and ``message``.

Registration
------------
Set in ``settings.py``::

    REST_FRAMEWORK = {
        ...
        'EXCEPTION_HANDLER': 'core.exceptions.custom_exception_handler',
    }
"""

import logging

from django.http import Http404
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    MethodNotAllowed,
    NotAuthenticated,
    NotFound,
    ParseError,
    PermissionDenied,
    Throttled,
    UnsupportedMediaType,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_default_handler

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HTTP status → human-readable label mapping
# ---------------------------------------------------------------------------
_STATUS_LABELS: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: 'Bad Request',
    status.HTTP_401_UNAUTHORIZED: 'Unauthorized',
    status.HTTP_403_FORBIDDEN: 'Forbidden',
    status.HTTP_404_NOT_FOUND: 'Not Found',
    status.HTTP_405_METHOD_NOT_ALLOWED: 'Method Not Allowed',
    status.HTTP_406_NOT_ACCEPTABLE: 'Not Acceptable',
    status.HTTP_408_REQUEST_TIMEOUT: 'Request Timeout',
    status.HTTP_409_CONFLICT: 'Conflict',
    status.HTTP_410_GONE: 'Gone',
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: 'Unsupported Media Type',
    status.HTTP_422_UNPROCESSABLE_ENTITY: 'Unprocessable Entity',
    status.HTTP_429_TOO_MANY_REQUESTS: 'Too Many Requests',
    status.HTTP_500_INTERNAL_SERVER_ERROR: 'Internal Server Error',
    status.HTTP_501_NOT_IMPLEMENTED: 'Not Implemented',
    status.HTTP_502_BAD_GATEWAY: 'Bad Gateway',
    status.HTTP_503_SERVICE_UNAVAILABLE: 'Service Unavailable',
}


def _label(http_status: int) -> str:
    return _STATUS_LABELS.get(http_status, 'Error')


def _flatten_errors(detail) -> dict | list | str:
    """Recursively unwrap DRF error detail into plain Python types.

    DRF wraps strings in ``ErrorDetail`` objects; this converts them back to
    plain strings so they serialise cleanly without custom JSON encoders.
    """
    if isinstance(detail, list):
        return [_flatten_errors(item) for item in detail]
    if isinstance(detail, dict):
        return {key: _flatten_errors(value) for key, value in detail.items()}
    return str(detail)


def _extract_message(detail) -> str:
    """Extract a single top-level human-readable message from DRF detail."""
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        if detail:
            return _extract_message(detail[0])
        return 'An error occurred.'
    if isinstance(detail, dict):
        # Prefer non_field_errors, then the first available key.
        if 'non_field_errors' in detail:
            return _extract_message(detail['non_field_errors'])
        if detail:
            first_value = next(iter(detail.values()))
            return _extract_message(first_value)
        return 'An error occurred.'
    return str(detail)


def custom_exception_handler(exc, context):
    """Main entry point registered via ``REST_FRAMEWORK['EXCEPTION_HANDLER']``.

    Converts Django's Http404 and PermissionDenied to their DRF equivalents
    before processing, then formats the final response into a consistent
    envelope structure.
    """
    # Convert Django native exceptions to DRF equivalents so they pass
    # through the standard DRF machinery first.
    if isinstance(exc, Http404):
        exc = NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = PermissionDenied()

    # Let DRF do its own processing (runs renderers, sets status, etc.).
    response = drf_default_handler(exc, context)

    if response is None:
        # Unhandled exception — log it and return a generic 500.
        logger.exception(
            'Unhandled exception in view %s',
            context.get('view', 'unknown'),
            exc_info=exc,
        )
        return Response(
            {
                'status': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'error': _label(status.HTTP_500_INTERNAL_SERVER_ERROR),
                'message': 'An unexpected server error occurred.',
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    http_status = response.status_code
    detail = exc.detail if hasattr(exc, 'detail') else str(exc)

    envelope: dict = {
        'status': http_status,
        'error': _label(http_status),
        'message': _extract_message(detail),
    }

    # Include field-level error detail for validation errors.
    if isinstance(exc, ValidationError):
        envelope['errors'] = _flatten_errors(detail)

    # Throttled: add retry information.
    if isinstance(exc, Throttled) and exc.wait is not None:
        envelope['message'] = (
            f'Request was throttled. Expected available in {exc.wait:.0f} second(s).'
        )
        envelope['retry_after'] = exc.wait

    response.data = envelope
    return response


# ---------------------------------------------------------------------------
# Named exception subclasses for use throughout the project
# ---------------------------------------------------------------------------

class DomainNotFound(NotFound):
    """Raised when the requested domain does not exist or is disabled."""
    default_detail = 'Domain not found or is not enabled.'
    default_code = 'domain_not_found'


class UserDisabled(AuthenticationFailed):
    """Raised when a user account exists but user_enabled=False."""
    default_detail = 'This user account has been disabled.'
    default_code = 'user_disabled'


class InvalidCredentials(AuthenticationFailed):
    """Raised for bad username/password combinations."""
    default_detail = 'Invalid username or password.'
    default_code = 'invalid_credentials'


class ProtectedResourceError(PermissionDenied):
    """Raised when an attempt is made to mutate a protected record."""
    default_detail = 'This resource is protected and cannot be modified or deleted.'
    default_code = 'protected_resource'


class CrossDomainAccessError(PermissionDenied):
    """Raised when a request attempts to access a resource in another domain."""
    default_detail = 'Cross-domain access is not permitted.'
    default_code = 'cross_domain_access'


class ConflictError(APIException):
    """HTTP 409 Conflict — used for duplicate-key or state-conflict errors."""
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'A conflict occurred with the current state of the resource.'
    default_code = 'conflict'
