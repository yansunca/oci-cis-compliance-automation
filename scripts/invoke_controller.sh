#!/usr/bin/env bash
set -euo pipefail

: "${CONTROLLER_FUNCTION_ID:?Set CONTROLLER_FUNCTION_ID from terraform output controller_function_id}"
: "${REGION:?Set REGION, for example us-ashburn-1}"
OUTPUT_FILE="${OUTPUT_FILE:-./build/controller-invoke-response.json}"

mkdir -p "$(dirname "$OUTPUT_FILE")"
oci fn function invoke   --function-id "$CONTROLLER_FUNCTION_ID"   --body '{}'   --file "$OUTPUT_FILE"   --region "$REGION"

cat "$OUTPUT_FILE"
printf '
'
