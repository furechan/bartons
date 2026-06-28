use pyo3::prelude::*;
use polars::prelude::*;
use pyo3_polars::PySeries;
use pyo3_polars::derive::polars_expr;
use pyo3::exceptions::PyRuntimeError;
use itertools::izip;

// True Range:
//   TR = max(high - low, |high - prev_close|, |low - prev_close|)
// The first bar (no previous close) uses high - low. A bar with a missing
// high or low yields null. No period/kwargs — TR is per-bar.
fn calc_trange(high: &Series, low: &Series, close: &Series) -> PolarsResult<Series> {
    let high = high.cast(&DataType::Float64)?;
    let low = low.cast(&DataType::Float64)?;
    let close = close.cast(&DataType::Float64)?;
    let h = high.f64()?;
    let l = low.f64()?;
    let c = close.f64()?;
    let name = "trange";

    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new(name.into(), h.len());
    let mut prev_close: Option<f64> = None;

    for (oh, ol, oc) in izip!(h.iter(), l.iter(), c.iter()) {
        match (oh, ol) {
            (Some(hi), Some(lo)) => {
                let mut tr = hi - lo;
                if let Some(pc) = prev_close {
                    tr = tr.max((hi - pc).abs()).max((lo - pc).abs());
                }
                builder.append_value(tr);
            }
            _ => builder.append_null(),
        }
        // The current close becomes the previous close for the next bar.
        prev_close = oc;
    }

    let output = builder.finish().into_series();

    Ok(output)
}

#[polars_expr(output_type = Float64)]
fn trange_expr(inputs: &[Series]) -> PolarsResult<Series> {
    calc_trange(&inputs[0], &inputs[1], &inputs[2])
}

#[pyfunction]
#[pyo3(signature = (high, low, close))]
pub fn trange(high: PySeries, low: PySeries, close: PySeries) -> PyResult<PySeries> {
    let high: Series = high.into();
    let low: Series = low.into();
    let close: Series = close.into();

    let result = match calc_trange(&high, &low, &close) {
        Ok(s) => s,
        Err(e) => return Err(PyRuntimeError::new_err(e.to_string())),
    };

    let result: PySeries = PySeries(result);
    Ok(result)
}
