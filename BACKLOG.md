# Backlog

Items decided or considered but not scheduled. Add new items at the end.

## Mintalib: STEP should skip NaNs

Change Mintalib's `STEP` so a NaN input emits NaN without changing the previous
finite output. The next finite input should resume stepping from that retained
state rather than reseeding the filter after the NaN.

## Mintalib: rename MAV to MA

Rename the generic moving-average dispatcher from `MAV` to the conventional
`MA`. The shorter name makes its relationship to the concrete `SMA`, `EMA`,
`WMA`, and other moving averages clearer. Consider retaining `MAV` temporarily
as a deprecated compatibility alias.
