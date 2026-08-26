/// One bar's `(high, low)`.
pub(crate) type HighLowInput = (Option<f64>, Option<f64>);

/// One bar's `(high, low, close)`.
pub(crate) type HighLowCloseInput = (Option<f64>, Option<f64>, Option<f64>);

/// One bar's `(source, volume)`.
pub(crate) type SourceVolumeInput = (Option<f64>, Option<f64>);

pub mod ema;
pub mod dema;
pub mod tema;
pub mod hma;
pub mod zlema;
pub mod mad;
pub mod rma;
pub mod sma;
pub mod wma;
pub mod rsi;
pub mod trange;
pub mod atr;
pub mod cci;
pub mod ker;
pub mod kama;
pub mod sar;
pub mod streak;
pub mod supertrend;
pub mod linreg;
pub mod quadreg;
pub mod mfi;
pub mod dmi;
pub mod alma;
pub mod aroon;
