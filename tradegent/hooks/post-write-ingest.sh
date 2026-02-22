#!/bin/bash
# Post-write hook for auto-ingesting knowledge documents
#
# Triggers after Write tool is used on files in tradegent_knowledge/knowledge/
# Automatically embeds in RAG and extracts to Graph.
#
# Input (JSON on stdin):
#   tool_input.file_path - absolute path to written file
#   tool_response.success - whether write succeeded
#
# Output (JSON):
#   additionalContext - feedback to Claude about ingestion

set -euo pipefail

# Read hook input from stdin
INPUT=$(cat)

# Extract variables using jq
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
SUCCESS=$(echo "$INPUT" | jq -r '.tool_response.success // "false"')

# Exit early if no file path or write failed
if [[ -z "$FILE_PATH" ]] || [[ "$SUCCESS" != "true" ]]; then
    exit 0
fi

# Only process knowledge YAML files
if [[ "$FILE_PATH" != *"tradegent_knowledge/knowledge/"* ]]; then
    exit 0
fi

if [[ "$FILE_PATH" != *.yaml ]] && [[ "$FILE_PATH" != *.yml ]]; then
    exit 0
fi

# Run the ingest script
SCRIPT_DIR="/opt/data/tradegent_swarm/tradegent/scripts"
INGEST_OUTPUT=$("$SCRIPT_DIR/ingest.py" "$FILE_PATH" --json 2>&1) || true

# Parse the result
RAG_SUCCESS=$(echo "$INGEST_OUTPUT" | jq -r '.rag.success // false')
GRAPH_SUCCESS=$(echo "$INGEST_OUTPUT" | jq -r '.graph.success // false')
RAG_CHUNKS=$(echo "$INGEST_OUTPUT" | jq -r '.rag.chunks // 0')
GRAPH_ENTITIES=$(echo "$INGEST_OUTPUT" | jq -r '.graph.entities // 0')

# Build status message
STATUS=""
if [[ "$RAG_SUCCESS" == "true" ]]; then
    STATUS="RAG: ${RAG_CHUNKS} chunks"
else
    STATUS="RAG: failed"
fi

if [[ "$GRAPH_SUCCESS" == "true" ]]; then
    STATUS="${STATUS}, Graph: ${GRAPH_ENTITIES} entities"
else
    STATUS="${STATUS}, Graph: failed"
fi

# Return context to Claude
cat <<EOF
{
  "additionalContext": "Auto-ingested to knowledge base: ${STATUS}"
}
EOF

exit 0
