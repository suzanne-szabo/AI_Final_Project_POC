#!/usr/bin/env bash
# HW-12 evaluation, night 2 (2026-11-16). Run from the repository root:
#
#     bash scripts/evening_eval.sh
#
# Reruns what the course key's $2/hour budget cut off on night 1, and evaluates D38. Every live run goes
# through scripts/paced_run.py: when the hourly budget is spent, the affected session is discarded, the
# script waits 10 minutes, and the session is rerun from scratch. Expected total: about 4 to 5 hours,
# mostly waiting for the budget window. LangSmith is off (free tier used up); the JSONL traces are the
# evidence. Protocol: docs/evaluation-protocol.md (see its change table for night 2).

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE="$ROOT/../final_project_baseline"   # git worktree at 3a00ed7 (created on night 1)
LOG="$ROOT/runs/evening-2026-11-16.log"
SEED=7
QWEN="Qwen3.8-Flash-Next"
GEMMA="Gemma-4-26B-A4B"

mkdir -p "$ROOT/runs"
log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

run() {  # run TREE NAME ARGS...: one paced run; output always goes to this repository's runs/
  local tree="$1" name="$2"; shift 2
  log "START $name"
  if (cd "$ROOT" && caffeinate -i uv run python scripts/paced_run.py --root "$tree" -- "$@" \
        --out "$ROOT/runs/$name") >>"$LOG" 2>&1; then
    log "DONE  $name"
  else
    log "FAILED $name (see the lines above in this log)"
  fi
}

[ -d "$BASE" ] || { log "baseline worktree missing at $BASE (git worktree add ../final_project_baseline 3a00ed7)"; exit 1; }
cp "$ROOT/.env" "$BASE/.env"
log "git: revised tree at $(git -C "$ROOT" rev-parse --short HEAD) (uncommitted files: $(git -C "$ROOT" status --short | wc -l | tr -d ' '))"

# --- offline, D38 code (minutes, no gateway): C2 and C6 for eig_explain with D38 -------------------
run "$ROOT" "eval-offline-500-noconf-d38"  --deciders eig_explain --students 500 --seed $SEED --no-use-confidence
run "$ROOT" "eval-offline-500-novague-d38" --deciders eig_explain --students 500 --seed $SEED --vague-answer-rate 0

# --- C3 again: D38 with the live interpreter, same 100 students as night 1 (~12 min) ----------------
run "$ROOT" "eval-d38-eigexplain-llm-100" --deciders eig_explain --interpreter llm --students 100 --seed $SEED

# --- C4 and C5: full agent, 50 students each --------------------------------------------------------
run "$BASE" "eval-baseline-qwen-50" --deciders interviewer --interviewer-model $QWEN --interpreter llm --students 50 --seed $SEED
run "$ROOT" "eval-d38-qwen-50"      --deciders interviewer --interviewer-model $QWEN --interpreter llm --students 50 --seed $SEED
run "$ROOT" "eval-d38-gemma-50"     --deciders interviewer --interviewer-model $GEMMA --interpreter llm --students 50 --seed $SEED

log "ALL DONE"
