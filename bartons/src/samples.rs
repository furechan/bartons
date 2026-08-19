//! Deterministic datasets shared by Rust and Python tests and benchmarks.

use std::f64::consts::TAU;

use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::error::PyPolarsErr;
use pyo3_polars::PyDataFrame;

const FIRST_DATE: i32 = 10_957; // 2000-01-01, in days since the Unix epoch.

/// Options for [`random_prices`].
#[derive(Clone, Copy, Debug)]
pub struct RandomPricesOptions {
    pub n_rows: usize,
    pub n_chunks: usize,
    pub n_tickers: usize,
    pub seed: u64,
    pub null_first: bool,
}

impl Default for RandomPricesOptions {
    fn default() -> Self {
        Self {
            n_rows: 10_000,
            n_chunks: 1,
            n_tickers: 1,
            seed: 0,
            null_first: false,
        }
    }
}

/// Return a frame with exactly `n_chunks` physical chunks in every column.
///
/// The input is first consolidated, so the result depends only on `n_chunks`,
/// not on the input's existing chunk boundaries. The evenly sized output
/// chunks are zero-copy slices of that consolidated frame.
pub fn with_n_chunks(frame: &DataFrame, n_chunks: usize) -> PolarsResult<DataFrame> {
    let total_rows = frame.height();
    polars_ensure!(total_rows > 0, InvalidOperation: "cannot chunk an empty DataFrame");
    polars_ensure!(
        (1..=total_rows).contains(&n_chunks),
        InvalidOperation: "n_chunks must be between 1 and {}", total_rows
    );

    let mut contiguous = frame.clone();
    contiguous.rechunk_mut();
    if n_chunks == 1 {
        return Ok(contiguous);
    }

    let quotient = total_rows / n_chunks;
    let remainder = total_rows % n_chunks;
    let mut offset = 0;
    let mut output: Option<DataFrame> = None;

    for chunk_index in 0..n_chunks {
        let size = quotient + usize::from(chunk_index < remainder);
        let chunk = contiguous.slice(offset as i64, size);
        match &mut output {
            Some(frame) => {
                frame.vstack_mut(&chunk)?;
            },
            None => output = Some(chunk),
        }
        offset += size;
    }

    Ok(output.expect("n_chunks is validated as positive"))
}

/// Generate deterministic OHLCV data with an exact physical chunk count.
///
/// `n_rows` is the number of bars per ticker. With multiple tickers the frame
/// has a leading `ticker` column and is ordered by `(ticker, date)`. Chunk
/// boundaries are distributed as evenly as possible over the final frame.
pub fn random_prices(options: RandomPricesOptions) -> PolarsResult<DataFrame> {
    let RandomPricesOptions {
        n_rows,
        n_chunks,
        n_tickers,
        seed,
        null_first,
    } = options;

    polars_ensure!(n_rows > 0, InvalidOperation: "n_rows must be positive");
    polars_ensure!(n_tickers > 0, InvalidOperation: "n_tickers must be positive");
    let total_rows = n_rows
        .checked_mul(n_tickers)
        .ok_or_else(|| polars_err!(InvalidOperation: "n_rows * n_tickers overflows usize"))?;
    polars_ensure!(
        (1..=total_rows).contains(&n_chunks),
        InvalidOperation: "n_chunks must be between 1 and {}", total_rows
    );
    polars_ensure!(
        n_rows <= (i32::MAX - FIRST_DATE) as usize,
        InvalidOperation: "n_rows is too large for the generated Date column"
    );

    let mut rng = Random64::new(seed);
    let mut open = Vec::with_capacity(n_rows);
    let mut high = Vec::with_capacity(n_rows);
    let mut low = Vec::with_capacity(n_rows);
    let mut close = Vec::with_capacity(n_rows);
    let mut volume = Vec::with_capacity(n_rows);
    let mut previous_close = 100.0_f64;

    for row in 0..n_rows {
        let open_value = previous_close;
        let close_value = (open_value * (1.0002 + 0.012 * rng.normal())).max(0.01);
        let spread = open_value * rng.uniform(0.001, 0.015);
        let high_value = open_value.max(close_value) + spread;
        let low_value = (open_value.min(close_value) - spread).max(0.01);
        let valid = !(null_first && row == 0);

        open.push(valid.then_some(open_value));
        high.push(valid.then_some(high_value));
        low.push(valid.then_some(low_value));
        close.push(valid.then_some(close_value));
        volume.push(rng.integer(100_000, 10_000_000) as i64);
        previous_close = close_value;
    }

    let ticker_names = (n_tickers > 1).then(|| {
        (0..n_tickers)
            .map(|index| format!("T{:03}", index + 1))
            .collect::<Vec<_>>()
    });
    let rows = 0..total_rows;
    let mut columns = Vec::with_capacity(6 + usize::from(n_tickers > 1));

    if let Some(names) = &ticker_names {
        columns.push(
            StringChunked::from_iter_values(
                "ticker".into(),
                rows.clone().map(|index| names[index / n_rows].as_str()),
            )
            .into_series()
            .into(),
        );
    }

    let dates = rows
        .clone()
        .map(|index| FIRST_DATE + (index % n_rows) as i32)
        .collect::<Vec<_>>();
    columns.push(
        Int32Chunked::from_vec("date".into(), dates)
            .into_date()
            .into_series()
            .into(),
    );
    columns.push(option_column(
        "open",
        rows.clone().map(|index| open[index % n_rows]),
    ));
    columns.push(option_column(
        "high",
        rows.clone().map(|index| high[index % n_rows]),
    ));
    columns.push(option_column(
        "low",
        rows.clone().map(|index| low[index % n_rows]),
    ));
    columns.push(option_column(
        "close",
        rows.clone().map(|index| close[index % n_rows]),
    ));
    columns.push(
        Int64Chunked::from_iter_values(
            "volume".into(),
            rows.map(|index| volume[index % n_rows]),
        )
        .into_series()
        .into(),
    );

    let frame = DataFrame::new(total_rows, columns)?;
    with_n_chunks(&frame, n_chunks)
}

fn option_column(name: &'static str, values: impl Iterator<Item = Option<f64>>) -> Column {
    Float64Chunked::from_iter_options(name.into(), values)
        .into_series()
        .into()
}

/// Generate deterministic OHLCV prices with controlled chunking.
///
/// Args:
///     n_rows: number of rows per ticker.
///     n_chunks: exact number of chunks in every output column.
///     n_tickers: number of price series.
///     seed: deterministic pseudo-random seed.
///     null_first: whether the first OHLC row of each ticker is null.
///
/// Returns:
///     A Polars DataFrame with the requested physical chunk layout.
#[pyfunction]
#[pyo3(
    name = "random_prices",
    signature = (n_rows=10_000, *, n_chunks=1, n_tickers=1, seed=0, null_first=false)
)]
pub fn random_prices_py(
    n_rows: usize,
    n_chunks: usize,
    n_tickers: usize,
    seed: u64,
    null_first: bool,
) -> PyResult<PyDataFrame> {
    let frame = random_prices(RandomPricesOptions {
        n_rows,
        n_chunks,
        n_tickers,
        seed,
        null_first,
    })
    .map_err(PyPolarsErr::from)?;
    Ok(PyDataFrame(frame))
}

/// Return a DataFrame with exactly the requested number of physical chunks.
///
/// Args:
///     frame: input DataFrame; its existing chunk layout is ignored.
///     n_chunks: exact number of chunks in every output column.
///
/// Returns:
///     A logically equivalent Polars DataFrame with controlled chunking.
#[pyfunction]
#[pyo3(name = "with_n_chunks", signature = (frame, n_chunks))]
pub fn with_n_chunks_py(frame: PyDataFrame, n_chunks: usize) -> PyResult<PyDataFrame> {
    with_n_chunks(&frame.0, n_chunks)
        .map(PyDataFrame)
        .map_err(PyPolarsErr::from)
        .map_err(Into::into)
}

/// Small deterministic PRNG so fixtures do not depend on a third-party RNG's
/// version-specific output sequence. Uses the non-cryptographic SplitMix64
/// algorithm.
struct Random64 {
    state: u64,
}

impl Random64 {
    fn new(seed: u64) -> Self {
        Self { state: seed }
    }

    fn next(&mut self) -> u64 {
        self.state = self.state.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut value = self.state;
        value = (value ^ (value >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        value = (value ^ (value >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        value ^ (value >> 31)
    }

    fn unit(&mut self) -> f64 {
        ((self.next() >> 11) as f64 + 0.5) * (1.0 / ((1_u64 << 53) as f64))
    }

    fn uniform(&mut self, low: f64, high: f64) -> f64 {
        low + (high - low) * self.unit()
    }

    fn normal(&mut self) -> f64 {
        (-2.0 * self.unit().ln()).sqrt() * (TAU * self.unit()).cos()
    }

    fn integer(&mut self, low: u64, high: u64) -> u64 {
        low + self.next() % (high - low + 1)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn creates_exact_chunks() -> PolarsResult<()> {
        let frame = random_prices(RandomPricesOptions {
            n_rows: 100,
            n_chunks: 7,
            n_tickers: 3,
            seed: 42,
            null_first: true,
        })?;

        assert_eq!(frame.height(), 300);
        assert!(frame.columns().iter().all(|column| column.n_chunks() == 7));
        Ok(())
    }

    #[test]
    fn chunk_layout_is_independent_of_input_layout() -> PolarsResult<()> {
        let contiguous = random_prices(RandomPricesOptions {
            n_rows: 100,
            ..Default::default()
        })?;
        let seven = with_n_chunks(&contiguous, 7)?;
        let three = with_n_chunks(&seven, 3)?;

        assert!(seven.columns().iter().all(|column| column.n_chunks() == 7));
        assert!(three.columns().iter().all(|column| column.n_chunks() == 3));
        assert!(contiguous.equals_missing(&three));
        Ok(())
    }
}
