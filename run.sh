#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  HZTZPrinter — Project Shell Script
#
#  EXECUTE:
#    ./run.sh setup        Install dependencies and create the virtual env
#    ./run.sh [args]       Run fool_printer.py with the given arguments
#    ./run.sh              Show fool_printer.py --help
#
#  SOURCE:
#    source run.sh         Activate the virtual environment in the current shell
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/venv"
PYTHON="${PYTHON:-python3}"

# Set libusb path on macOS (Homebrew Apple Silicon)
_set_dyld() {
    if [ "$(uname -s)" = "Darwin" ] && [ -d "/opt/homebrew/lib" ]; then
        export DYLD_LIBRARY_PATH="/opt/homebrew/lib${DYLD_LIBRARY_PATH:+:${DYLD_LIBRARY_PATH}}"
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
#  SOURCED — activate venv in the caller's shell
# ─────────────────────────────────────────────────────────────────────────────
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
    if [ ! -d "${VENV_DIR}" ]; then
        echo "❌ No virtual environment found. Run: bash ${BASH_SOURCE[0]} setup"
        return 1
    fi
    # shellcheck disable=SC1091
    source "${VENV_DIR}/bin/activate"
    _set_dyld
    echo "HZTZPrinter environment activated.  Type 'deactivate' to exit."
    return 0
fi

# ─────────────────────────────────────────────────────────────────────────────
#  EXECUTED
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail
cd "${SCRIPT_DIR}"

# Colour helpers (disabled when stdout is not a terminal)
if [ -t 1 ]; then
    _G='\033[0;32m' _Y='\033[0;33m' _C='\033[0;36m' _R='\033[0;31m' _B='\033[1m' _0='\033[0m'
else
    _G='' _Y='' _C='' _R='' _B='' _0=''
fi
info() { printf "${_C}[INFO]${_0}  %s\n" "$*"; }
ok()   { printf "${_G}[OK]${_0}    %s\n" "$*"; }
warn() { printf "${_Y}[WARN]${_0}  %s\n" "$*"; }
err()  { printf "${_R}[ERR]${_0}   %s\n" "$*" >&2; }

# ── setup ────────────────────────────────────────────────────────────────────
cmd_setup() {
    printf "\n${_B}  HZTZPrinter — Setup${_0}\n\n"

    # Python
    if ! command -v "$PYTHON" &>/dev/null; then
        err "Python 3 not found. Install it or override with: PYTHON=/path/to/python3 ./run.sh setup"
        exit 1
    fi
    ok "Python: $("$PYTHON" --version 2>&1)"

    # libusb (macOS only)
    if [[ "$OSTYPE" == darwin* ]]; then
        if command -v brew &>/dev/null; then
            if ! brew list libusb &>/dev/null 2>&1; then
                warn "libusb not found via Homebrew."
                read -rp "  Install it now? [y/N] " _ans
                if [[ "$_ans" =~ ^[Yy]$ ]]; then
                    brew install libusb && ok "libusb installed."
                else
                    warn "Skipped — USB communication may fail without libusb."
                fi
            else
                ok "libusb available."
            fi
        else
            warn "Homebrew not found — ensure libusb is installed manually."
        fi
    fi

    # Virtual environment
    if [ -d "venv" ]; then
        read -rp "  Virtual environment already exists. Recreate? [y/N] " _ans
        [[ "$_ans" =~ ^[Yy]$ ]] && { info "Removing old venv…"; rm -rf venv; }
    fi
    if [ ! -d "venv" ]; then
        info "Creating virtual environment…"
        "$PYTHON" -m venv venv
        ok "Virtual environment created."
    fi

    # Dependencies
    # shellcheck disable=SC1091
    source venv/bin/activate
    info "Upgrading pip…"
    pip install --upgrade pip --quiet
    if [ -f "requirements.txt" ]; then
        info "Installing dependencies…"
        pip install -r requirements.txt
        ok "Dependencies installed."
    else
        warn "requirements.txt not found — skipping."
    fi

    printf "\n  ${_G}${_B}Setup complete!${_0}\n\n"
    echo "  Activate:  source run.sh"
    echo "  Run:       ./run.sh --help"
    echo ""
}

# ── dispatch ─────────────────────────────────────────────────────────────────
case "${1:-}" in
    setup)
        cmd_setup
        ;;
    *)
        if [ ! -d "${VENV_DIR}" ]; then
            err "Virtual environment not found. Run: ./run.sh setup"
            exit 1
        fi
        # shellcheck disable=SC1091
        source "${VENV_DIR}/bin/activate"
        _set_dyld
        if [ $# -eq 0 ]; then
            exec python3 "${SCRIPT_DIR}/fool_printer.py" --help
        else
            exec python3 "${SCRIPT_DIR}/fool_printer.py" "$@"
        fi
        ;;
esac
