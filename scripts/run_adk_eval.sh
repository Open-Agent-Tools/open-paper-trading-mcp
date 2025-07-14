#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "▶️  Running ADK Evaluation..."

if [ -z "$GOOGLE_API_KEY" ]; then
    echo "⚠️  Warning: GOOGLE_API_KEY is not set in the environment. The evaluation may fail."
fi

# The first argument to the script is the eval file, or a default is used.
EVAL_FILE=${1:-"tests/evals/list_available_tools_test.json"}

# Run the evaluation, passing all arguments.
adk eval examples/google_adk_agent "$@" --config_file_path tests/evals/test_config.json

echo "✅ Evaluation complete."