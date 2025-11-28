import asyncio
import datetime
from datetime import timedelta
from unittest import mock

import pytest

from mcp.client.cache import CacheEntry


def test_cache_entry_initial_state():
    """Test that a new CacheEntry is invalid."""
    cache = CacheEntry()
    assert not cache.is_valid
    assert cache.get() is None


def test_cache_entry_set_and_get():
    """Test setting and getting data from CacheEntry."""
    cache = CacheEntry()
    with mock.patch("datetime.datetime", wraps=datetime.datetime) as mock_datetime:
        mock_datetime.now.return_value = datetime.datetime.fromtimestamp(0)
        cache.set({"key": "test_data"}, timedelta(seconds=10))
        mock_datetime.now.return_value = datetime.datetime.fromtimestamp(5)
        assert cache.is_valid
        assert cache.get() == {"key": "test_data"}


def test_cache_entry_expired():
    """Test that CacheEntry expires correctly."""
    cache = CacheEntry()
    with mock.patch("datetime.datetime", wraps=datetime.datetime) as mock_datetime:
        mock_datetime.now.return_value = datetime.datetime.fromtimestamp(0)
        cache.set({"key": "test_data"}, timedelta(seconds=10))
        mock_datetime.now.return_value = datetime.datetime.fromtimestamp(11)
        assert not cache.is_valid
        assert cache.get() is None


@pytest.mark.anyio
async def test_cache_entry_expiry_callback():
    """Test that the expiry callback is called."""
    callback = mock.AsyncMock()
    cache = CacheEntry(on_expired=callback)
    cache.set({"key": "test_data"}, timedelta(seconds=0.1))
    assert cache.is_valid
    await asyncio.sleep(0.2)
    assert not cache.is_valid
    callback.assert_called_once()


@pytest.mark.anyio
async def test_cache_entry_set_with_zero_ttl():
    """Test setting cache with zero TTL."""
    cache = CacheEntry()
    with mock.patch("datetime.datetime", wraps=datetime.datetime) as mock_datetime:
        mock_datetime.now.return_value = datetime.datetime.fromtimestamp(0)
        cache.set({"key": "test_data"}, timedelta(seconds=0))
    assert not cache.is_valid
    assert cache.get() is None


@pytest.mark.anyio
async def test_cache_entry_set_with_negative_ttl():
    """Test setting cache with negative TTL."""
    cache = CacheEntry()
    with mock.patch("datetime.datetime", wraps=datetime.datetime) as mock_datetime:
        mock_datetime.now.return_value = datetime.datetime.fromtimestamp(0)
        cache.set({"key": "test_data"}, timedelta(seconds=-1))
    assert not cache.is_valid
    assert cache.get() is None


@pytest.mark.anyio
async def test_cancel_expiry_task():
    """Test cancelling the expiry task."""
    callback = mock.AsyncMock()
    cache = CacheEntry(on_expired=callback)
    with mock.patch("datetime.datetime", wraps=datetime.datetime) as mock_datetime:
        mock_datetime.now.return_value = datetime.datetime.fromtimestamp(0)
        cache.set({"key": "test_data"}, timedelta(seconds=0.1))
    cache.cancel_expiry_task()
    await asyncio.sleep(0.2)
    callback.assert_not_called()


@pytest.mark.anyio
async def test_cache_entry_refresh_before_expiry():
    """Test that refreshing a CacheEntry before expiry works correctly."""
    callback = mock.AsyncMock()
    cache = CacheEntry(on_expired=callback)

    # Set initial expiry in 0.5 seconds
    cache.set({"key": "test_data"}, timedelta(seconds=0.5))
    assert cache.is_valid

    # Wait for 0.3 seconds, before the initial expiry
    await asyncio.sleep(0.3)
    assert cache.is_valid
    callback.assert_not_called()

    # Refresh the cache, setting a new expiry 0.5 seconds from now
    cache.set({"key": "test_data"}, timedelta(seconds=0.5))

    # Wait for another 0.3 seconds. Total elapsed: 0.6 seconds.
    # This is past the original 0.5 second expiry, but before the new expiry (0.3 + 0.5 = 0.8)
    await asyncio.sleep(0.3)
    assert cache.is_valid
    callback.assert_not_called()

    # Wait for another 0.3 seconds. Total elapsed: 0.9 seconds.
    # This is past the new expiry (0.8 seconds).
    await asyncio.sleep(0.3)
    assert not cache.is_valid
    callback.assert_called_once()
