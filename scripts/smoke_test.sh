#!/usr/bin/env bash
# End-to-end smoke test for the arXiv Paper Curator API.
# Exercises every endpoint against a running `docker compose up` stack.
#
# Usage: bash scripts/smoke_test.sh [BASE_URL]
#   BASE_URL defaults to http://localhost:8000

set -uo pipefail

BASE_URL="${1:-http://localhost:8000}"
API="$BASE_URL/api/v1"
PASS=0
FAIL=0

# ---- helpers ---------------------------------------------------------

section() {
  echo ""
  echo "=== $1 ==="
}

# check <label> <expected_status> <curl args...>
# Runs curl, prints the response, and pass/fails on HTTP status.
check() {
  local label="$1" expected="$2"
  shift 2
  local resp status body
  resp="$(curl -s -o /tmp/smoke_body.$$ -w "%{http_code}" --max-time 120 "$@")"
  status="$resp"
  body="$(cat /tmp/smoke_body.$$ 2>/dev/null)"
  rm -f /tmp/smoke_body.$$

  if [ "$status" = "$expected" ]; then
    echo "[PASS] $label -> $status"
    PASS=$((PASS + 1))
  else
    echo "[FAIL] $label -> expected $expected, got $status"
    FAIL=$((FAIL + 1))
  fi
  echo "$body" | head -c 500
  echo ""
}

# extract a JSON field with grep/sed (no jq dependency)
extract() {
  echo "$1" | grep -o "\"$2\":\"[^\"]*\"" | head -1 | sed "s/\"$2\":\"//;s/\"$//"
}

echo "Smoke-testing $BASE_URL"

# ---- 1. Health ---------------------------------------------------------

section "1. Health check"
check "GET /health" 200 "$API/health"

# ---- 2. Papers (Week 2) -------------------------------------------------

section "2. Papers listing"
check "GET /papers/" 200 "$API/papers/?limit=3"

# ---- 3. BM25 search (Week 3) --------------------------------------------

section "3. BM25 search"
check "POST /search/" 200 -X POST "$API/search/" \
  -H "Content-Type: application/json" \
  -d '{"query":"attention mechanism","size":3}'

# ---- 4. Hybrid search (Week 4) -------------------------------------------

section "4. Hybrid search (BM25 + vector + RRF)"
check "POST /hybrid-search/" 200 -X POST "$API/hybrid-search/" \
  -H "Content-Type: application/json" \
  -d '{"query":"neural network architecture","size":3,"use_hybrid":true}'

# ---- 5. RAG generation (Week 5/6) ----------------------------------------

section "5. /ask (non-streaming RAG)"
ASK_RESP="$(curl -s --max-time 90 -X POST "$API/ask" \
  -H "Content-Type: application/json" \
  -d '{"query":"What is a transformer model?","top_k":2,"use_hybrid":true,"model":"gemma3:4b"}')"
echo "$ASK_RESP" | head -c 600
echo ""
if echo "$ASK_RESP" | grep -q '"answer"'; then
  echo "[PASS] /ask returned an answer"
  PASS=$((PASS + 1))
else
  echo "[FAIL] /ask did not return an answer"
  FAIL=$((FAIL + 1))
fi

section "5b. /ask exact-match cache (Redis) - second call should be near-instant"
T0=$(date +%s%N)
curl -s --max-time 90 -X POST "$API/ask" \
  -H "Content-Type: application/json" \
  -d '{"query":"What is a transformer model?","top_k":2,"use_hybrid":true,"model":"gemma3:4b"}' > /dev/null
T1=$(date +%s%N)
MS=$(( (T1 - T0) / 1000000 ))
echo "Cached call took ${MS}ms"
if [ "$MS" -lt 3000 ]; then
  echo "[PASS] cache hit (< 3s)"
  PASS=$((PASS + 1))
else
  echo "[WARN] slower than expected for a cache hit - check Redis"
fi

section "6. /stream (SSE streaming RAG)"
STREAM_OUT="$(curl -s --max-time 90 -X POST "$API/stream" \
  -H "Content-Type: application/json" \
  -d '{"query":"What is deep learning?","top_k":2,"model":"gemma3:4b"}')"
if echo "$STREAM_OUT" | grep -q '"done": true' || echo "$STREAM_OUT" | grep -q '"done":true'; then
  echo "[PASS] /stream completed with done:true"
  PASS=$((PASS + 1))
else
  echo "[FAIL] /stream did not complete cleanly"
  FAIL=$((FAIL + 1))
fi
echo "$STREAM_OUT" | tail -c 300

# ---- 7. Agentic RAG (Week 7 - LangGraph) ---------------------------------

section "7a. /ask-agentic - in-scope query (should retrieve and answer)"
AGENTIC_RESP="$(curl -s --max-time 120 -X POST "$API/ask-agentic" \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the attention mechanism in transformer architectures?","top_k":3,"use_hybrid":true,"model":"gemma3:4b"}')"
echo "$AGENTIC_RESP" | head -c 600
echo ""
TRACE_ID="$(extract "$AGENTIC_RESP" "trace_id")"
if echo "$AGENTIC_RESP" | grep -q '"reasoning_steps"'; then
  echo "[PASS] /ask-agentic returned reasoning_steps (trace_id=$TRACE_ID)"
  PASS=$((PASS + 1))
else
  echo "[FAIL] /ask-agentic missing reasoning_steps"
  FAIL=$((FAIL + 1))
fi

section "7b. /ask-agentic - out-of-scope query (guardrail should refuse)"
OOS_RESP="$(curl -s --max-time 60 -X POST "$API/ask-agentic" \
  -H "Content-Type: application/json" \
  -d '{"query":"What is your favorite pizza topping?","model":"gemma3:4b"}')"
echo "$OOS_RESP" | head -c 400
echo ""
if echo "$OOS_RESP" | grep -q '"retrieval_attempts":0' || echo "$OOS_RESP" | grep -q '"retrieval_attempts": 0'; then
  echo "[PASS] guardrail correctly rejected the out-of-scope query"
  PASS=$((PASS + 1))
else
  echo "[WARN] expected retrieval_attempts:0 for an out-of-scope query - check guardrail scoring"
fi

section "7c. /feedback - score the in-scope trace above"
if [ -n "${TRACE_ID:-}" ]; then
  check "POST /feedback" 200 -X POST "$API/feedback" \
    -H "Content-Type: application/json" \
    -d "{\"trace_id\":\"$TRACE_ID\",\"score\":1.0,\"comment\":\"smoke test\"}"
else
  echo "[SKIP] no trace_id captured from 7a, skipping feedback test"
fi

# ---- Summary --------------------------------------------------------------

section "Summary"
echo "Passed: $PASS"
echo "Failed: $FAIL"
if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
