#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# TARS-AI — setup & run (micromamba)
# ============================================================
# Creates/reuses a micromamba environment, installs deps, does a
# quick OMLX reachability preflight, then launches TARS pointed at
# your local OMLX server.
#
# Both the LLM and the TTS run on OMLX (OpenAI-compatible MLX
# server): the LLM via /v1/chat/completions, the voice via
# /v1/audio/speech. Nothing runs locally except audio playback,
# so this works from any OS. Use --no-voice to skip TTS.
# ============================================================

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

ENV_NAME="${TARS_ENV_NAME:-tars-ai}"
PYTHON_VERSION="${TARS_PYTHON_VERSION:-3.12}"
MICROMAMBA_BIN="${MICROMAMBA_BIN:-}"
SKIP_INSTALL="${TARS_SKIP_INSTALL:-false}"
SKIP_RUN="${TARS_SKIP_RUN:-false}"
NO_VOICE="${TARS_NO_VOICE:-false}"

# OMLX connection (same env names as strix-omlx). main.py also reads these,
# but we pass them explicitly so the launch banner shows exactly what's used.
OMLX_URL="${OMLX_URL:-${LLM_API_BASE:-http://127.0.0.1:8000/v1}}"
OMLX_API_KEY="${OMLX_API_KEY:-${LLM_API_KEY:-test}}"
OMLX_MODEL="${OMLX_MODEL:-${STRIX_LLM:-Qwen3.6-27B-bf16}}"
OMLX_TTS_MODEL="${OMLX_TTS_MODEL:-Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16}"

ARGS=()

usage() {
    cat <<EOF
Usage: $(basename "$0") [--no-voice] [--no-run] [--skip-install]
                        [--model ID] [--tts-model ID] [--omlx-url URL] [--api-key KEY]
                        [--] [main.py args...]

Flags:
  --no-voice        Run text-only (skip TTS)
  --no-run          Set up the env and stop before launching
  --skip-install    Reuse the env as-is, skip pip install
  --model ID        LLM id as served by OMLX (default: ${OMLX_MODEL})
  --tts-model ID    TTS id as served by OMLX (default: ${OMLX_TTS_MODEL})
  --omlx-url URL    OMLX /v1 endpoint (default: ${OMLX_URL})
  --api-key KEY     OMLX Bearer key (default: ${OMLX_API_KEY})
  --                Pass everything after this straight to main.py
  -h, --help        Show this help

Environment overrides:
  TARS_ENV_NAME         micromamba env name (default: tars-ai)
  TARS_PYTHON_VERSION   Python version for a new env (default: 3.12)
  TARS_SKIP_INSTALL     true to skip pip install
  TARS_SKIP_RUN         true to skip launching TARS
  TARS_NO_VOICE         true to force text-only
  MICROMAMBA_BIN        explicit path to the micromamba binary
  OMLX_URL / LLM_API_BASE, OMLX_API_KEY / LLM_API_KEY, OMLX_MODEL / STRIX_LLM, OMLX_TTS_MODEL
EOF
}

while (($#)); do
    case "$1" in
        --no-voice)     NO_VOICE="true"; shift ;;
        --no-run)       SKIP_RUN="true"; shift ;;
        --skip-install) SKIP_INSTALL="true"; shift ;;
        --model)        OMLX_MODEL="${2:?--model needs a value}"; shift 2 ;;
        --tts-model)    OMLX_TTS_MODEL="${2:?--tts-model needs a value}"; shift 2 ;;
        --omlx-url)     OMLX_URL="${2:?--omlx-url needs a value}"; shift 2 ;;
        --api-key)      OMLX_API_KEY="${2:?--api-key needs a value}"; shift 2 ;;
        -h|--help)      usage; exit 0 ;;
        --)             shift; ARGS+=("$@"); break ;;
        *)              ARGS+=("$1"); shift ;;
    esac
done

# ── pretty step runner ───────────────────────────────────────────────────
run_step() {
    local description="$1"; shift
    printf '\n\033[1;36m==>\033[0m %s\n' "${description}"
    if "$@"; then
        printf '\033[1;32m    ✓ done\033[0m\n'
    else
        local rc=$?
        printf '\033[1;31m    ✗ failed (exit %d)\033[0m\n' "${rc}" >&2
        exit "${rc}"
    fi
}

resolve_micromamba() {
    if [[ -n "${MICROMAMBA_BIN}" ]]; then
        [[ -x "${MICROMAMBA_BIN}" ]] || { echo "MICROMAMBA_BIN is not executable: ${MICROMAMBA_BIN}" >&2; exit 1; }
        return
    fi
    if command -v micromamba >/dev/null 2>&1; then
        MICROMAMBA_BIN="$(command -v micromamba)"
    elif [[ -x "/usr/local/mamba/bin/micromamba" ]]; then
        MICROMAMBA_BIN="/usr/local/mamba/bin/micromamba"
    elif [[ -x "${HOME}/micromamba/bin/micromamba" ]]; then
        MICROMAMBA_BIN="${HOME}/micromamba/bin/micromamba"
    else
        echo "micromamba was not found in PATH or common install locations." >&2
        echo "Install it, e.g.:  brew install micromamba" >&2
        echo "             or:   curl -Ls https://micro.mamba.pm/install.sh | bash" >&2
        exit 1
    fi
}

micromamba_run() {
    "${MICROMAMBA_BIN}" run -n "${ENV_NAME}" "$@"
}

# ── OMLX preflight (non-fatal: OMLX loads models on demand) ───────────────
_check_model_served() {
    local body="$1" model="$2" label="$3"
    if printf '%s' "${body}" | grep -Fq "\"${model}\""; then
        printf '    ✓ %s served: %s\n' "${label}" "${model}"
    else
        printf '\033[1;33m    ! %s model "%s" not in the served list — must match GET /models exactly, or OMLX returns 404.\033[0m\n' "${label}" "${model}"
    fi
}

omlx_preflight() {
    local models_url="${OMLX_URL%/}/models"
    printf '\n\033[1;36m==>\033[0m Checking OMLX at %s\n' "${OMLX_URL}"
    local body
    if ! body="$(curl -fsS -H "Authorization: Bearer ${OMLX_API_KEY}" "${models_url}" 2>/dev/null)"; then
        local dash="${OMLX_URL%/v1}"
        printf '\033[1;33m    ! OMLX not reachable yet. Start it, then TARS will connect on first message.\033[0m\n'
        printf '      Dashboard: %s/admin/dashboard\n' "${dash}"
        return 0
    fi
    printf '\033[1;32m    ✓ OMLX is responding\033[0m\n'
    _check_model_served "${body}" "${OMLX_MODEL}" "LLM"
    if [[ "${NO_VOICE}" != "true" ]]; then
        _check_model_served "${body}" "${OMLX_TTS_MODEL}" "TTS"
    fi
}

# ── main ─────────────────────────────────────────────────────────────────
cd "${SCRIPT_DIR}"
resolve_micromamba

if ! "${MICROMAMBA_BIN}" env list | awk '{print $1}' | grep -Fxq "${ENV_NAME}"; then
    run_step "Creating micromamba environment ${ENV_NAME} with Python ${PYTHON_VERSION}" \
        "${MICROMAMBA_BIN}" create -n "${ENV_NAME}" "python=${PYTHON_VERSION}" -y
else
    echo "Using existing micromamba environment: ${ENV_NAME}"
fi

if [[ "${SKIP_INSTALL}" != "true" ]]; then
    run_step "Upgrading pip" micromamba_run python -m pip install --upgrade pip
    run_step "Installing requirements.txt" micromamba_run python -m pip install -r requirements.txt
fi

omlx_preflight

if [[ "${SKIP_RUN}" == "true" ]]; then
    echo ""
    echo "Setup complete. Skipping launch (--no-run or TARS_SKIP_RUN=true)."
    echo "Run manually with:"
    echo "  ${MICROMAMBA_BIN} run -n ${ENV_NAME} python main.py --model ${OMLX_MODEL}"
    exit 0
fi

LAUNCH=(python main.py --omlx-url "${OMLX_URL}" --api-key "${OMLX_API_KEY}" --model "${OMLX_MODEL}" --tts-model "${OMLX_TTS_MODEL}")
if [[ "${NO_VOICE}" == "true" ]]; then
    LAUNCH+=(--no-voice)
fi
# User passthrough args come last so they override the defaults above.
LAUNCH+=(${ARGS[@]+"${ARGS[@]}"})

run_step "Launching TARS (${OMLX_MODEL} via ${OMLX_URL})" micromamba_run "${LAUNCH[@]}"
