FROM python:3.13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.local/bin:$PATH"
