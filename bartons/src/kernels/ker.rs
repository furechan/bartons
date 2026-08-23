use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::derive::polars_expr;
use pyo3_polars::error::PyPolarsErr;
use pyo3_polars::PySeries;
use serde::Deserialize;

use crate::ring_buffer::RingBuffer;
use crate::utils::{run_filter, Filter};

#[derive(Deserialize)]
pub struct KerKwargs {
    period: i64,
}

/// Streaming Kaufman Efficiency Ratio filter, fed one value at a time via
/// [`Filter::next`].
///
///   KER = |value - oldest| / Σ|change|
///
/// over a window of `period` changes — the net distance travelled divided by
/// the path length walked to get there. The result is in `0..=1`: 1 for a
/// window that moved in one direction without retracing, near 0 for one that
/// churned. [`KamaFilter`] uses it to interpolate its smoothing constant.
///
/// **Absolute, not signed.** The numerator is the *magnitude* of the net move,
/// following TA-Lib and Kaufman's original. bearta's `KER` divides the signed
/// sum instead, giving `-1..=1`; that folds direction into the ratio, which
/// reads well standalone but makes KAMA's smoothing constant asymmetric — a
/// perfect downtrend would smooth more slowly than a perfect rally. Since one
/// kernel serves both surfaces here, it takes the definition KAMA needs.
///
/// **Deliberately does not match mintalib**, which bartons otherwise follows.
/// mintalib's `calc_ker` spans `period - 1` changes in the numerator against
/// `period` in the denominator, so its ratio is systematically low and its KAMA
/// correspondingly slow. The tell is a monotone ramp, which is perfectly
/// efficient by definition: this kernel returns exactly 1.0, mintalib returns
/// 0.833 at `period = 3` and drifts further down as the period grows.
/// `test_trend_and_chop_bracket_the_smoothing` pins the 1.0.
///
/// A window of `period` changes spans `period + 1` values, so that is the ring
/// buffer's length and the warmup: the first output lands on the row at index
/// `period`.
///
/// A null resets the window *and* the previous value, so the change spanning a
/// gap is never formed. This is the windowed convention (SMA, WMA, MAD) rather
/// than the recursive one, and it is a deliberate divergence from both mintalib
/// and bearta, which carry the previous value across a gap and let the window
/// span it. Resetting makes this kernel agree exactly with the natural polars
/// spelling — `src.diff().rolling_sum(period, min_samples=period)` over the same
/// window — which is pinned by `test_ker_matches_native_polars`.
///
/// Σ|change| is kept as a running sum, but the numerator is taken from the two
/// endpoint values rather than a running signed sum: Σchange telescopes to
/// `value - oldest`, so reading the endpoints is both cheaper and immune to the
/// cancellation a running signed sum would accumulate over a long series.
///
/// [`KamaFilter`]: crate::kernels::kama::KamaFilter
pub struct KerFilter {
    buffer: RingBuffer<f64>,
    volatility: f64,
}

impl KerFilter {
    pub fn new(period: i64) -> Result<Self, String> {
        if period <= 0 {
            return Err("KER period must be > 0".to_string());
        }
        Ok(Self {
            // `period` changes span `period + 1` values.
            buffer: RingBuffer::new(period as usize + 1),
            volatility: 0.0,
        })
    }

    fn reset(&mut self) {
        self.buffer.clear();
        self.volatility = 0.0;
    }
}

impl Filter for KerFilter {
    type Input = Option<f64>;
    type Output = f64;

    fn next(&mut self, input: Option<f64>) -> Option<f64> {
        let Some(value) = input else {
            self.reset();
            return None;
        };

        let previous = self.buffer.newest().copied();
        let evicted = self.buffer.push(value);

        if let Some(previous) = previous {
            self.volatility += (value - previous).abs();
        }
        if let Some(evicted) = evicted {
            let oldest = *self.buffer.oldest().expect("full buffer has an oldest");
            self.volatility -= (oldest - evicted).abs();
        }

        if !self.buffer.is_full() {
            return None;
        }

        let oldest = *self.buffer.oldest().expect("full buffer has an oldest");
        let direction = (value - oldest).abs();
        // A window that never moved has no path length either. Both references
        // call that perfectly efficient rather than undefined.
        Some(if self.volatility == 0.0 {
            1.0
        } else {
            direction / self.volatility
        })
    }
}

fn ker(series: &Series, period: i64) -> PolarsResult<Series> {
    let filter = KerFilter::new(period).map_err(|e| PolarsError::InvalidOperation(e.into()))?;
    run_filter(series, "ker", filter)
}

#[polars_expr(output_type = Float64)]
fn ker_expr(inputs: &[Series], kwargs: KerKwargs) -> PolarsResult<Series> {
    ker(&inputs[0], kwargs.period)
}

/// Kaufman Efficiency Ratio.
///
/// The net move over a window divided by the total distance travelled within
/// it, in 0..=1.
///
/// Args:
///     series: input values.
///     period: number of changes in the window (default 10).
///
/// Returns:
///     A Float64 series; null during the warmup period.
#[pyfunction]
#[pyo3(name = "ker", signature = (series, *, period=10))]
pub fn ker_py(series: PySeries, period: i64) -> PyResult<PySeries> {
    let series: Series = series.into();
    let result = ker(&series, period).map_err(PyPolarsErr::from)?;
    Ok(PySeries(result))
}
