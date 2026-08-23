use crate::utils::{Pair, Triple};

/// One bar's `(high, low)` — the indicator-side name for
/// [`Pair`](crate::utils::Pair).
pub(crate) type Hl = Pair;

/// One bar's `(high, low, close)` — the indicator-side name for
/// [`Triple`](crate::utils::Triple).
///
/// The drivers in `utils` stay arity-generic (they only know they are fed three
/// aligned series); the kernels here say what those three are. Same type, so an
/// `Hlc` selects the three-Float64-source [`FilterInput`](crate::utils::FilterInput)
/// implementation used by `run_filter`.
pub(crate) type Hlc = Triple;

pub mod ema;
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
pub mod linreg;
