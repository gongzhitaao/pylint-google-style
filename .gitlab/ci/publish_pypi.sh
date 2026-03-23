#!/usr/bin/env bash
# Publish to PyPI if the minor or major version has changed.
set -euo pipefail

if python .gitlab/ci/version_bumped.py; then
  uv build
  uv publish \
    --publish-url "${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/packages/pypi" \
    --token "$CI_JOB_TOKEN"
fi
