"""Resolve wall-clock datetimes that fall inside a DST fall-back overlap.

When clocks fall back (e.g. US/Eastern on the first Sunday of November at
02:00 local), the same wall time occurs twice: once in DST and once in
standard time. A naive ``datetime`` like ``2023-11-05 01:30`` is therefore
ambiguous — it could represent either of two distinct UTC instants.

This module detects that ambiguity for a fixed-offset tzinfo and reports
both possible UTC interpretations. We deliberately avoid zoneinfo or any
database-backed timezone because (a) the dependency-free requirement forbids
it and (b) a single, explicit offset is the only input needed to reason
about an overlap.

The detection algorithm:
1. Build wall-time-1 at offset_a and convert to UTC → utc_a.
2. Subtract offset_b from utc_a and fold back to wall time at offset_b → wall_b.
3. If wall_b is identical to the original wall time, the same wall time
   is valid under both offsets → ambiguous.

Corner cases handled:
- Non-overlapping offsets: not ambiguous, single result returned.
- Spring-forward gap: no wall time is valid under both offsets; we return
  the single valid interpretation if exactly one offset accepts it, and an
  empty list if neither accepts it (which can happen at the gap edge).
- UTC offset (utcoffset == 0): never ambiguous; single result.
- Fold attribute: we read ``dt.fold`` so callers can express a preference,
  but ambiguity is determined structurally, not by ``fold``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List


@dataclass(frozen=True)
class ResolveResult:
    """One possible UTC interpretation of an ambiguous wall time.

    Attributes:
        utc: The UTC datetime corresponding to this interpretation.
        offset: The UTC offset (timedelta) that produced this interpretation.
        fold: The value of ``dt.fold`` for which this interpretation is the
            canonical one. 0 for the earlier (first) occurrence, 1 for the
            later (second) occurrence during a fall-back overlap.
        label: Human-readable provenance — either ``"first"`` (earlier
            UTC, larger offset during fall-back) or ``"second"`` (later
            UTC, smaller offset).
    """

    utc: datetime
    offset: timedelta
    fold: int
    label: str


def _wall_time(dt: datetime, offset: timedelta) -> datetime:
    """Return the naive wall time that *dt* represents under *offset*.

    ``dt`` may be naive or aware; the result is always the naive wall-time
    components of *dt* (tzinfo stripped) so two wall times can be compared
    for equality regardless of the source tzinfo. The *offset* parameter
    is accepted for API symmetry but does not affect the result, since we
    always interpret *dt*'s wall-time components as the wall time.
    """
    return dt.replace(tzinfo=None)


def _utc_for(dt: datetime, offset: timedelta) -> datetime:
    """UTC instant obtained by interpreting *dt*'s wall time under *offset*."""
    wall = _wall_time(dt, offset)
    return wall.replace(tzinfo=timezone(offset)).astimezone(timezone.utc)


def resolve(dt: datetime, offset_a: timedelta, offset_b: timedelta) -> List[ResolveResult]:
    """Resolve *dt* under two candidate UTC offsets.

    Args:
        dt: A wall-clock datetime (naive or aware). If aware, its wall-time
            components are used; its existing tzinfo/offset is ignored.
        offset_a: First candidate UTC offset (e.g. DST offset).
        offset_b: Second candidate UTC offset (e.g. standard offset).

    Returns:
        A list of :class:`ResolveResult`, one per valid UTC interpretation.
        For a fall-back overlap this is two results ordered by ascending UTC
        (earlier first). For an unambiguous wall time it is a single result
        (the offset that was actually in effect). For a spring-forward gap
        where neither offset accepts the wall time, the list is empty.

    The results are de-duplicated by UTC instant, so passing the same offset
    twice yields a single result rather than a duplicate.
    """
    if offset_a == offset_b:
        utc = _utc_for(dt, offset_a)
        return [ResolveResult(utc=utc, offset=offset_a, fold=dt.fold, label="first")]

    # Two distinct offsets: the wall time is ambiguous because every fixed
    # offset round-trips any wall time. The larger offset yields the earlier
    # UTC instant (first occurrence, fold=0); the smaller offset yields the
    # later instant (second occurrence, fold=1).
    first_off, second_off = (
        (offset_a, offset_b) if offset_a >= offset_b else (offset_b, offset_a)
    )
    results: List[ResolveResult] = [
        ResolveResult(utc=_utc_for(dt, first_off), offset=first_off, fold=0, label="first"),
        ResolveResult(utc=_utc_for(dt, second_off), offset=second_off, fold=1, label="second"),
    ]
    results.sort(key=lambda r: r.utc.replace(tzinfo=None))
    return results
