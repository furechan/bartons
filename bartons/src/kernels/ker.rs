use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::derive::polars_expr;
use pyo3_polars::error::PyPolarsErr;
use pyo3_polars::PySeries;
use serde::Deserialize;

use crate::utils::{run_unary, Filter};

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
    buf: Vec<f64>,
    idx: usize,
    count: i64,
    volatility: f64,
}

impl KerFilter {
    pub fn new(period: i64) -> Result<Self, String> {
        if period <= 0 {
            return Err("KER period must be > 0".to_string());
        }
        Ok(Self {
            // `period` changes span `period + 1` values.
            buf: vec![0.0; period as usize + 1],
            idx: 0,
            count: 0,
            volatility: 0.0,
        })
    }

    fn reset(&mut self) {
        self.idx = 0;
        self.count = 0;
        self.volatility = 0.0;
    }
}

impl Filter for KerFilter {
    type Input = Option<f64>;

    fn next(&mut self, input: Option<f64>) -> Option<f64> {
        let Some(value) = input else {
            self.reset();
            return None;
        };

        let cap = self.buf.len();
        let full = self.count >= cap as i64;

        // Both reads have to happen before the write, which overwrites the
        // oldest slot.
        if self.count > 0 {
            let prev = self.buf[(self.idx + cap - 1) % cap];
            self.volatility += (value - prev).abs();
        }
        if full {
            // The oldest value is leaving, and with it the change from it to
            // its successor.
            let oldest = self.buf[self.idx];
            let successor = self.buf[(self.idx + 1) % cap];
            self.volatility -= (successor - oldest).abs();
        }

        self.buf[self.idx] = value;
        self.idx = (self.idx + 1) % cap;
        if !full {
            self.count += 1;
        }

        if self.count < cap as i64 {
            return None;
        }

        // The ring is full, so the write above advanced `idx` onto the oldest
        // value still in the window.
        let direction = (value - self.buf[self.idx]).abs();
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
    run_unary(series, "ker", filter)
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
