# ambiguous-wall_time_resolver

Detects `datetime` values that fall within a DST fall-back overlap and reports all possible UTC interpretations.

```python
from datetime import datetime, timedelta
from ambiguous_wall_time_resolver import resolve

dt = datetime(2023, 11, 5, 1, 30)  # US/Eastern fall-back
for r in resolve(dt, timedelta(hours=-4), timedelta(hours=-5)):
    print(r.label, r.utc, r.offset)
# first  2023-11-05 05:30:00+00:00 -4:00:00
# second 2023-11-05 06:30:00+00:00 -5:00:00
```

## Why

A naive wall-clock `datetime` that lands inside a fall-back overlap maps to two different UTC instants. Most libraries force you to pick one (via `fold`) and silently discard the other. This library returns both, ordered by ascending UTC, so callers can decide explicitly.

The trade-off: we work with **fixed offsets only**. There is no timezone database access, no IANA lookup, no historical rules. You supply the two offsets that bracket the overlap (e.g. `-04:00` for EDT and `-05:00` for EST). This keeps the library dependency-free and deterministic; the cost is that the caller must know which offsets apply.

## Edge you will hit

**Spring-forward gaps.** A wall time like `02:30` during a spring-forward does not exist, but every fixed offset will round-trip it — so this library cannot structurally detect gaps. The result for a gap is a single interpretation (the offset that was actually in effect), not an empty list. If you need gap detection, use `zoneinfo` and check `fold` semantics; that is outside this library's scope.

## Exports

- `resolve(dt, offset_a, offset_b) -> list[ResolveResult]` — resolves *dt* under two candidate UTC offsets.
- `ResolveResult` — frozen dataclass with `utc: datetime`, `offset: timedelta`, `fold: int`, `label: str` (`"first"` = earlier UTC, `"second"` = later UTC).

## Design notes

The window stores values eagerly rather than keeping running aggregates. Running
sums drift with floating point over long streams, and recomputing from a small
buffer is cheap enough that the drift is not worth the speed.

## Limitations

Values are coerced to floats, so very large integers lose precision. If you need
exact integer aggregates over a window, this is the wrong tool.

