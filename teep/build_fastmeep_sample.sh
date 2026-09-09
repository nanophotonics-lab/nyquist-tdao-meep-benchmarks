#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
: "${CONDA_PREFIX:?Activate the target Conda environment before building}"
CONDA_ENV_PREFIX="${CONDA_PREFIX}"
PYTHON_BIN="${PYTHON_BIN:-${CONDA_ENV_PREFIX}/bin/python}"

export PATH="${CONDA_ENV_PREFIX}/bin:${PATH}"

"${PYTHON_BIN}" - <<'PY'
import os
import sys
import meep as mp

if os.path.realpath(sys.prefix) != os.path.realpath(os.environ["CONDA_PREFIX"]):
    raise SystemExit(
        f"Python prefix {sys.prefix!r} does not match CONDA_PREFIX "
        f"{os.environ['CONDA_PREFIX']!r}"
    )
if mp.with_mpi():
    raise SystemExit(
        "This build script targets the archived nompi PyMeep environment; "
        "refusing to mix it with an MPI Meep build."
    )
PY

EXT_SUFFIX="$("${PYTHON_BIN}" -c 'import sysconfig; print(sysconfig.get_config_var("EXT_SUFFIX"))')"
PY_INCLUDE="$("${PYTHON_BIN}" -c 'import sysconfig; print(sysconfig.get_config_var("INCLUDEPY"))')"
NP_INCLUDE="$("${PYTHON_BIN}" -c 'import numpy; print(numpy.get_include())')"
CXX_CONFIG="${CXX:-$("${PYTHON_BIN}" -c 'import sysconfig; print(sysconfig.get_config_var("CXX"))')}"
read -r -a CXX_COMMAND <<< "${CXX_CONFIG}"
if [[ ${#CXX_COMMAND[@]} -eq 0 ]] || ! command -v "${CXX_COMMAND[0]}" >/dev/null 2>&1; then
    echo "C++ compiler not found: ${CXX_CONFIG}" >&2
    echo "Install/retain the environment.yml cxx-compiler dependency." >&2
    exit 2
fi

"${CXX_COMMAND[@]}" -O3 -std=c++17 -shared -fPIC \
  -I"${PY_INCLUDE}" \
  -I"${NP_INCLUDE}" \
  -I"${CONDA_ENV_PREFIX}/include" \
  "${SCRIPT_DIR}/fastmeep_sample.cpp" \
  -L"${CONDA_ENV_PREFIX}/lib" \
  -Wl,-rpath,"${CONDA_ENV_PREFIX}/lib" \
  -lmeep \
  -o "${SCRIPT_DIR}/fastmeep_sample${EXT_SUFFIX}"

echo "Built ${SCRIPT_DIR}/fastmeep_sample${EXT_SUFFIX}"
PYTHONPATH="${SCRIPT_DIR}/.." "${PYTHON_BIN}" - <<'PY'
import teep

teep.require_native_sampler()
print("Verified teep native sampler import and required benchmark symbols")
PY
