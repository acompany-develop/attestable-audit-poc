# Gramine SGX enclave for Python script auditing.
FROM gramineproject/gramine:1.9-noble@sha256:bdf2d0ef9bd09fa10684e14fbe822236df35708d58a852209c5f235842ecb6d7

WORKDIR /enclave
COPY enclave/* /enclave/

# Bandit + transitive deps go into a dedicated dir so the trust set is
# explicit and MRENCLAVE pins exactly these files.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --break-system-packages --no-cache-dir --target /enclave/pypkgs -r /enclave/requirements.txt

RUN chmod +x /enclave/entrypoint.sh \
 && mkdir -p /enclave/input /enclave/output

# PoC-only signing key. Replace with a managed key for anything real.
RUN gramine-sgx-gen-private-key

# Build & sign the manifest at image build time so MRENCLAVE is fixed
# per image (input/output dirs are sgx.allowed_files and don't affect it).
RUN make SGX=1

# Extract MRENCLAVE so verifiers can retrieve it without re-running gramine-sgx-sign.
RUN gramine-sgx-sigstruct-view --output-format json auditor.sig \
      | python3 -c 'import json,sys;print(json.load(sys.stdin)["mr_enclave"])' \
      > /enclave/mrenclave.hex

ENTRYPOINT ["/enclave/entrypoint.sh"]
