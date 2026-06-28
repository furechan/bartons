use pyo3::prelude::*;
use polars::prelude::*;
use serde::Deserialize;
use pyo3_polars::PySeries;
use pyo3_polars::derive::polars_expr;
use pyo3::exceptions::PyRuntimeError;

#[derive(Deserialize)]
pub struct WmaKwargs {
    period: i64,
}

fn calc_wma(series: &Series, period: i64) -> PolarsResult<Series> {
    let series = series.cast(&DataType::Float64)?;
    let ca = series.f64()?;
    let len = ca.len();
    let name = "wma";

    if period <= 0 {
        return Err(PolarsError::ComputeError("WMA period must be > 0".into()));
    }

    let p = period as usize;
    let denom = period as f64 * (period as f64 + 1.0) / 2.0; // sum of weights 1..period
    let mut buf = vec![0.0f64; p]; // ring buffer of the current run's window
    let mut idx = 0usize; // next write slot == oldest element once full
    let mut count: i64 = 0;
    let mut rsum = 0.0f64; // running simple sum of the window
    let mut wsum = 0.0f64; // running weighted sum (oldest weight 1 .. newest weight period)
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new(name.into(), len);

    for opt_val in ca.iter() {
        // A null breaks the current run: reset, emit null, and continue.
        let Some(val) = opt_val else {
            rsum = 0.0;
            wsum = 0.0;
            count = 0;
            idx = 0;
            builder.append_null();
            continue;
        };

        count += 1;
        rsum += val;
        wsum += count as f64 * val;

        if count > period {
            // Slide the window: drop one from every weight, then evict the oldest.
            let oldest = buf[idx]; // read before overwriting
            wsum -= rsum;
            rsum -= oldest;
            count -= 1;
        }
        buf[idx] = val;
        idx = (idx + 1) % p;

        // Warmup period emits null; otherwise the weighted mean.
        if count >= period {
            builder.append_value(wsum / denom);
        } else {
            builder.append_null();
        }
    }

    let output = builder.finish().into_series();

    Ok(output)
}

#[polars_expr(output_type = Float64)]
fn wma_expr(inputs: &[Series], kwargs: WmaKwargs) -> PolarsResult<Series> {
    calc_wma(&inputs[0], kwargs.period)
}

#[pyfunction]
#[pyo3(signature = (series, *, period=20))]
pub fn wma(series: PySeries, period: i64) -> PyResult<PySeries> {
    let series: Series = series.into();

    let result = match calc_wma(&series, period) {
        Ok(s) => s,
        Err(e) => return Err(PyRuntimeError::new_err(e.to_string())),
    };

    let result: PySeries = PySeries(result);
    Ok(result)
}
