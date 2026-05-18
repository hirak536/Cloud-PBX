"""
Global cache version utility.

All pbx: and client: cache keys embed a version number retrieved from Redis.
Calling bump() increments that version, making every existing cached response
stale in O(1) — no key scanning or deletion needed.
"""

from django.core.cache import cache

_VERSION_KEY = 'pbx:global_version'


def get() -> int:
    v = cache.get(_VERSION_KEY)
    if v is None:
        cache.set(_VERSION_KEY, 1, timeout=None)
        return 1
    return int(v)


def bump() -> int:
    """Increment the global version and return the new value."""
    try:
        new = cache.incr(_VERSION_KEY)
    except ValueError:
        # Key missing — initialise then increment
        cache.set(_VERSION_KEY, 1, timeout=None)
        new = 1
    return new
