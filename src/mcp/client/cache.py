"""Client-side cache utility."""

import asyncio
from datetime import timedelta
import datetime
from typing import Any, Callable, Coroutine

ExpiryCallback = Callable[[], Coroutine[Any, Any, None]]


class CacheEntry:
  """Holds a cached value with a TTL."""

  def __init__(self, on_expired: ExpiryCallback | None = None):
    self._data: dict[str, Any] | None = None
    self._expiry_time: datetime.datetime = datetime.datetime.min
    self._on_expired = on_expired
    self._expiry_task_handler: asyncio.TimerHandle | None = None

  @property
  def is_valid(self) -> bool:
    """Return True if cache holds data and is not expired."""
    return datetime.datetime.now() < self._expiry_time

  def get(self) -> dict[str, Any] | None:
    """Return cached data if valid, otherwise None."""
    if self.is_valid:
      return self._data
    return None

  def set(self, data: dict[str, Any], ttl: timedelta):
    """Set cache data with a TTL."""
    self.cancel_expiry_task()
    self._data = data
    self._expiry_time = datetime.datetime.now() + ttl
    if ttl > timedelta(seconds=0) and self._on_expired:
      loop = asyncio.get_running_loop()
      self._expiry_task_handler = loop.call_later(
          ttl.total_seconds(), self._run_expiry_callback
      )

  def _run_expiry_callback(self):
    """Runs the expiry callback."""
    self._data = None
    if self._on_expired:
      asyncio.create_task(self._on_expired())
    self._expiry_task_handler = None

  def cancel_expiry_task(self):
    """Cancels the pending expiry task."""
    if self._expiry_task_handler:
      self._expiry_task_handler.cancel()
      self._expiry_task_handler = None
