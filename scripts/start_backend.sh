#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  . "${ROOT_DIR}/.env"
  set +a
fi

if [[ -z "${VISION_TRAIN_PROJECTS_DIR:-}" ]]; then
  echo "VISION_TRAIN_PROJECTS_DIR 未设置，请在 .env 或环境变量中指定项目根目录"
  exit 1
fi

if [[ -z "${VISION_TRAIN_PRETRAINED_MODELS_DIR:-}" ]]; then
  echo "VISION_TRAIN_PRETRAINED_MODELS_DIR 未设置，请在 .env 或环境变量中指定预训练模型根目录"
  exit 1
fi

export PYTHONPATH="${ROOT_DIR}/src/web:${ROOT_DIR}/src:${PYTHONPATH:-}"

if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
  PYTHON_BIN="${PYTHON_BIN:-${ROOT_DIR}/.venv/bin/python}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

exec "${PYTHON_BIN}" src/web/main.py
