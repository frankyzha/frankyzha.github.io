#!/usr/bin/env bash
#SBATCH --job-name=collarai-gemma
#SBATCH --partition=compsci-gpu
#SBATCH --gres=gpu:a5000:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
# A short lease backfills quickly; Slurm signals and requeues it before expiry.
#SBATCH --time=23:50:00
#SBATCH --output=/usr/project/xtmp/yz1075/CollarAI/logs/gemma-server-%j.log
#SBATCH --signal=B:USR1@90
#SBATCH --requeue

set -euo pipefail

readonly ROOT=/usr/project/xtmp/yz1075/CollarAI
readonly SERVER="$ROOT/vendor/llama.cpp/build-cuda-12.1/bin/llama-server"
readonly MODEL="$ROOT/models/gemma-4-26b-a4b-q4/gemma-4-26B_q4_0-it.gguf"
readonly MMPROJ="$ROOT/models/gemma-4-26b-a4b-q4/gemma-4-26B-it-mmproj.gguf"
readonly API_KEYS="$ROOT/.secrets/llama-api-keys"

mkdir -p "$ROOT/logs"

child_pid=""
requeue() {
  if [[ -n "$child_pid" ]]; then
    kill -TERM "$child_pid" 2>/dev/null || true
    wait "$child_pid" 2>/dev/null || true
  fi
  scontrol requeue "$SLURM_JOB_ID"
  exit 0
}
trap requeue USR1

srun "$SERVER" \
  --model "$MODEL" \
  --mmproj "$MMPROJ" \
  --alias gemma-4-26b-a4b-it \
  --host 0.0.0.0 \
  --port 18083 \
  --api-key-file "$API_KEYS" \
  --ctx-size 131072 \
  --parallel 1 \
  --threads 8 \
  --n-gpu-layers 99 \
  --flash-attn on \
  --jinja &
child_pid=$!
wait "$child_pid"
