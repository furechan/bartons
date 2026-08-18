# Backlog

Items decided or considered but not scheduled. Add new items at the end.

## Rust


## Tooling

- Tag release commits. Nothing in git currently marks which commit a published version came from, since the version carries no `.dev` marker and no tag is cut. Revisit alongside the mintalib/mplchart publish-path review rather than diverging here first.
- Consider loading bundled samples with `pl.read_csv(..., rechunk=True)`. Do this
  only after the controlled `random_prices(..., n_chunks=...)` generator has
  replaced the accidental CSV chunk topology in chunk-sensitivity benchmarks,
  so changing the sample loader cannot erase the benchmark fixture.
