#!/bin/bash
set -euo pipefail

usage() {
  cat >&2 <<EOF
usage: docker run --device /dev/sgx_enclave --device /dev/sgx_provision \\
                  -v /var/run/aesmd:/var/run/aesmd \\
                  -v <host_workdir>:/work \\
                  <image> /work/<script.py> [/work/<output_dir>]

Inputs:
  \$1  path (inside container) of the Python script to audit
  \$2  optional output directory (default: /work/output)
EOF
  exit 2
}

[ $# -ge 1 ] || usage

INPUT_SCRIPT="$1"
OUTPUT_DIR="${2:-/work/output}"

[ -f "$INPUT_SCRIPT" ] || { echo "input not found: $INPUT_SCRIPT" >&2; exit 1; }

cp "$INPUT_SCRIPT" /enclave/input/script.py
rm -f /enclave/output/audit_result.json /enclave/output/quote.bin

cd /enclave
gramine-sgx auditor

mkdir -p "$OUTPUT_DIR"
cp /enclave/output/audit_result.json "$OUTPUT_DIR/"
cp /enclave/output/quote.bin         "$OUTPUT_DIR/"

echo "wrote: $OUTPUT_DIR/audit_result.json"
echo "wrote: $OUTPUT_DIR/quote.bin"
