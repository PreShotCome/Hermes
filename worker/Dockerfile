# Reference-mode Pearl worker: pure-Python matmul PoUW, no GPU required.
#
# Live mining (submitting ZK proofs to a real pearld node) additionally needs
# the official Pearl stack (pearl_mining, pearl-gateway) and a CUDA GPU — build
# that from github.com/pearl-research-labs/pearl; see worker/README.md.
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .
ENTRYPOINT ["pearl-worker"]
