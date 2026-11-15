#!/usr/bin/env bash
# HW-12 overnight evaluation (bank students, live course models). Run from the repository root:
#
#     bash scripts/overnight_eval.sh
#
# It compares the HW-11 baseline code (commit 3a00ed7, before D34) with the revised code (this working
# tree) on the same seeded students, and compares the Qwen and Gemma interviewers. Every run writes its
# own folder under runs/ with traces, summary and manifest. A failed run is logged and the script moves
# on to the next one. Expected total: about 4 to 4.5 hours. The protocol these runs follow is docs/evaluation-protocol.md. Keep the laptop on power; `caffeinate -i`
# stops macOS from sleeping while the script runs.
#
# Prompt cache: every run reuses one constant system prompt and tool list per role, so runs of the same
# role and model share a cached prefix. Runs are ordered so that runs of the same model and role follow
# each other.

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE="$ROOT/../final_project_baseline"   # git worktree at the HW-11 commit
DAY="2026-11-15"
LOG="$ROOT/runs/overnight-$DAY.log"
N=100
SEED=7
QWEN="Qwen3.8-Flash-Next"
GEMMA="Gemma-4-26B-A4B"

mkdir -p "$ROOT/runs"
log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

run() {  # run DIR NAME ARGS...: one evaluation run, logged, never stops the script
  local dir="$1" name="$2"; shift 2
  log "START $name"
  if (cd "$dir" && caffeinate -i uv run python -m mm_agent.run "$@" --out "$ROOT/runs/$name") >>"$LOG" 2>&1; then
    log "DONE  $name"
  else
    log "FAILED $name (see the lines above in this log)"
  fi
}

# --- the baseline worktree (created once) --------------------------------------------------------------
if [ ! -d "$BASE" ]; then
  log "creating baseline worktree at 3a00ed7"
  git -C "$ROOT" worktree add "$BASE" 3a00ed7 >>"$LOG" 2>&1 || { log "worktree failed"; exit 1; }
fi
cp "$ROOT/.env" "$BASE/.env"   # course key and LangSmith settings; .env is gitignored in both trees

log "git: revised tree at $(git -C "$ROOT" rev-parse --short HEAD) (plus uncommitted changes: $(git -C "$ROOT" status --short | wc -l | tr -d ' ') files)"

# --- 1. offline (no gateway, minutes): E1 adaptive vs fixed, E2 explanations and confidence ------------
run "$ROOT" "eval-offline-500"            --deciders fixed shuffled eig eig_explain --students 500 --seed $SEED
run "$ROOT" "eval-offline-500-noconf"     --deciders eig eig_explain --students 500 --seed $SEED --no-use-confidence
# C6 robustness (docs/evaluation-protocol.md): the same students with no vague or hedged answers
run "$ROOT" "eval-offline-500-novague"    --deciders eig eig_explain --students 500 --seed $SEED --vague-answer-rate 0

# R6 unsupported input on the revised code (seconds; expected to end ERROR / MODEL_ERROR)
run "$ROOT" "eval-unsupported" --deciders interviewer --interviewer-model NoSuchModel --students 1 --seed $SEED

# --- 2. the refinement (D34) in isolation: same code decider, live interpreter, old vs new prompt -------
run "$BASE" "eval-baseline-eigexplain-llm-$N" --deciders eig_explain --interpreter llm --students $N --seed $SEED
run "$ROOT" "eval-revised-eigexplain-llm-$N"  --deciders eig_explain --interpreter llm --students $N --seed $SEED

# --- 3. the full agent: Qwen interviewer, baseline vs revised; then Gemma (revised) ---------------------
run "$BASE" "eval-baseline-qwen-$N" --deciders interviewer --interviewer-model $QWEN --interpreter llm --students $N --seed $SEED
run "$ROOT" "eval-revised-qwen-$N"  --deciders interviewer --interviewer-model $QWEN --interpreter llm --students $N --seed $SEED
run "$ROOT" "eval-revised-gemma-$N" --deciders interviewer --interviewer-model $GEMMA --interpreter llm --students $N --seed $SEED

log "ALL DONE"
