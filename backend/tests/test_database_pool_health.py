"""Regression test: pool health knobs must stay enabled on both engines.

Stale connections in the SQLAlchemy pool produce intermittent
`could not receive data from server` errors. `pool_pre_ping` validates
each connection at checkout; `pool_recycle` ages them out before the
idle-kill window. If either flag gets dropped these tests fail loudly.
"""

from models.database import engine, sync_engine


def test_async_engine_pre_ping_enabled():
    assert engine.pool._pre_ping is True


def test_async_engine_recycle_set():
    assert engine.pool._recycle == 1800


def test_sync_engine_pre_ping_enabled():
    assert sync_engine.pool._pre_ping is True


def test_sync_engine_recycle_set():
    assert sync_engine.pool._recycle == 1800
