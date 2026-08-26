use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::derive::polars_expr;
use pyo3_polars::error::PyPolarsErr;
use pyo3_polars::PySeries;
use serde::Deserialize;

use super::atr::AtrFilter;
use super::HighLowCloseInput;
use crate::utils::{run_filter, Filter, FilterOutput};

#[derive(Deserialize)]
pub struct SupertrendKwargs {
    period: i64,
    multiplier: f64,
}

pub(crate) struct SupertrendOutput {
    supertrend: Option<f64>,
    direction: Option<i64>,
}

pub(crate) struct SupertrendBuilder {
    name: PlSmallStr,
    supertrend: PrimitiveChunkedBuilder<Float64Type>,
    direction: PrimitiveChunkedBuilder<Int64Type>,
}

impl FilterOutput for SupertrendOutput {
    type Builder = SupertrendBuilder;

    fn builder(name: &str, capacity: usize) -> Self::Builder {
        SupertrendBuilder {
            name: name.into(),
            supertrend: PrimitiveChunkedBuilder::new("supertrend".into(), capacity),
            direction: PrimitiveChunkedBuilder::new("direction".into(), capacity),
        }
    }

    fn append(builder: &mut Self::Builder, value: Option<Self>) {
        let value = value.unwrap_or(SupertrendOutput {
            supertrend: None,
            direction: None,
        });
        builder.supertrend.append_option(value.supertrend);
        builder.direction.append_option(value.direction);
    }

    fn finish(builder: Self::Builder) -> Series {
        let fields = [
            builder.supertrend.finish().into_series(),
            builder.direction.finish().into_series(),
        ];
        StructChunked::from_series(builder.name, fields[0].len(), fields.iter())
            .expect("equal-length Supertrend fields")
            .into_series()
    }
}

/// Streaming Supertrend filter with a fused Wilder ATR.
pub struct SupertrendFilter {
    atr: AtrFilter,
    multiplier: f64,
    upper: Option<f64>,
    lower: Option<f64>,
    direction: Option<i64>,
    previous_close: Option<f64>,
}

impl SupertrendFilter {
    pub fn new(period: i64, multiplier: f64) -> Result<Self, String> {
        if !multiplier.is_finite() || multiplier <= 0.0 {
            return Err("Supertrend multiplier must be finite and > 0".to_string());
        }
        Ok(Self {
            atr: AtrFilter::new(period)?,
            multiplier,
            upper: None,
            lower: None,
            direction: None,
            previous_close: None,
        })
    }
}

impl Filter for SupertrendFilter {
    type Input = HighLowCloseInput;
    type Output = SupertrendOutput;

    fn next(&mut self, (high, low, close): HighLowCloseInput) -> Option<Self::Output> {
        let atr = self.atr.next((high, low, close));
        let previous_close = self.previous_close;
        self.previous_close = close;

        let (high, low, close, atr) = high
            .zip(low)
            .zip(close)
            .zip(atr)
            .map(|(((high, low), close), atr)| (high, low, close, atr))?;

        let midpoint = (high + low) / 2.0;
        let basic_upper = midpoint + self.multiplier * atr;
        let basic_lower = midpoint - self.multiplier * atr;

        let upper = match (self.upper, previous_close) {
            (Some(previous), Some(close)) if basic_upper >= previous && close <= previous => {
                previous
            },
            _ => basic_upper,
        };
        let lower = match (self.lower, previous_close) {
            (Some(previous), Some(close)) if basic_lower <= previous && close >= previous => {
                previous
            },
            _ => basic_lower,
        };

        let direction = match self.direction {
            None => -1,
            Some(-1) if close > upper => 1,
            Some(1) if close < lower => -1,
            Some(direction) => direction,
        };
        let supertrend = if direction == 1 { lower } else { upper };

        self.upper = Some(upper);
        self.lower = Some(lower);
        self.direction = Some(direction);

        Some(SupertrendOutput {
            supertrend: Some(supertrend),
            direction: Some(direction),
        })
    }
}

fn supertrend(
    high: &Series,
    low: &Series,
    close: &Series,
    period: i64,
    multiplier: f64,
) -> PolarsResult<Series> {
    let filter = SupertrendFilter::new(period, multiplier)
        .map_err(|e| PolarsError::InvalidOperation(e.into()))?;
    run_filter((high, low, close), "supertrend", filter)
}

fn supertrend_output(_input_fields: &[Field]) -> PolarsResult<Field> {
    Ok(Field::new(
        "supertrend".into(),
        DataType::Struct(vec![
            Field::new("supertrend".into(), DataType::Float64),
            Field::new("direction".into(), DataType::Int64),
        ]),
    ))
}

#[polars_expr(output_type_func = supertrend_output)]
fn supertrend_expr(inputs: &[Series], kwargs: SupertrendKwargs) -> PolarsResult<Series> {
    supertrend(
        &inputs[0],
        &inputs[1],
        &inputs[2],
        kwargs.period,
        kwargs.multiplier,
    )
}

/// Supertrend trend-following line and direction.
///
/// Args:
///     high: high prices.
///     low: low prices.
///     close: close prices.
///     period: Wilder ATR period (default 10).
///     multiplier: positive ATR band multiplier (default 3.0).
///
/// Returns:
///     A Struct series with Float64 `supertrend` and Int64 `direction` fields.
#[pyfunction]
#[pyo3(name = "supertrend", signature = (high, low, close, *, period=10, multiplier=3.0))]
pub fn supertrend_py(
    high: PySeries,
    low: PySeries,
    close: PySeries,
    period: i64,
    multiplier: f64,
) -> PyResult<PySeries> {
    let result = supertrend(&high.into(), &low.into(), &close.into(), period, multiplier)
        .map_err(PyPolarsErr::from)?;
    Ok(PySeries(result))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn initializes_bearish() {
        let mut filter = SupertrendFilter::new(2, 1.0).unwrap();
        assert!(filter.next((Some(10.0), Some(8.0), Some(9.0))).is_none());
        let value = filter.next((Some(11.0), Some(9.0), Some(10.0))).unwrap();
        assert_eq!(value.direction, Some(-1));
        assert_eq!(value.supertrend, Some(12.0));
    }

    #[test]
    fn rejects_invalid_multiplier() {
        assert!(SupertrendFilter::new(10, 0.0).is_err());
        assert!(SupertrendFilter::new(10, f64::NAN).is_err());
    }
}
