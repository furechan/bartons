#!/usr/bin/env bash
#
# Install the evcxr Rust Jupyter kernel at the system / user level.
# Requires a Rust toolchain (cargo) and a C compiler.
#
set -euo pipefail

cargo install evcxr_jupyter
evcxr_jupyter --install

