#!/usr/bin/env bash
#
# Install the evcxr Rust Jupyter kernel at the system / user level.
#
# This deliberately ignores any active project virtualenv so the kernel is
# registered for the whole user account:
#   - the binary goes to ~/.cargo/bin
#   - the "rust" kernelspec goes to the user-level Jupyter data dir
#     (e.g. ~/.local/share/jupyter/kernels on Linux)
# and NOT inside a local .venv.
#
# Requires a Rust toolchain (cargo) and a C compiler.
#
set -euo pipefail

# --- Ensure we are not installing into a project virtualenv -----------------
if [[ -n "${VIRTUAL_ENV:-}" ]]; then
  echo "Active virtualenv detected: $VIRTUAL_ENV"
  echo "Excluding it so the kernel installs at the user level."
  # Drop "$VIRTUAL_ENV/bin" from PATH (one entry per line, exact match).
  PATH=$(printf '%s' "$PATH" | tr ':' '\n' | grep -vxF "$VIRTUAL_ENV/bin" | paste -sd ':' -)
  unset VIRTUAL_ENV
fi
unset CONDA_PREFIX 2>/dev/null || true

# Make sure cargo's bin dir is on PATH, both to find cargo and to pick up the
# freshly installed evcxr_jupyter binary for step 2.
export PATH="$HOME/.cargo/bin:$PATH"

command -v cargo >/dev/null || {
  echo "error: cargo not found. Install Rust from https://rustup.rs" >&2
  exit 1
}
echo "Using cargo: $(command -v cargo)"

# --- 1. Build & install the evcxr Jupyter kernel binary (user-level) --------
echo "==> cargo install evcxr_jupyter"
cargo install evcxr_jupyter

# --- 2. Register the "rust" kernelspec (user-level) -------------------------
echo "==> evcxr_jupyter --install"
evcxr_jupyter --install

# --- Verify -----------------------------------------------------------------
echo "==> Verifying installation"
if command -v jupyter >/dev/null; then
  jupyter kernelspec list || true
fi
for d in "$HOME/.local/share/jupyter/kernels/rust" "$HOME/Library/Jupyter/kernels/rust"; do
  [[ -d "$d" ]] && echo "Installed 'rust' kernel at: $d"
done

echo "Done."
