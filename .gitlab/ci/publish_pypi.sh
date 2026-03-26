#!/usr/bin/env bash
# Publish to PyPI when no package exists on the registry yet, or when
# the minor/major version has been bumped.
set -euo pipefail

if python .gitlab/ci/should_publish.py; then
  uv build
  uv publish \
    --publish-url "${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/packages/pypi" \
    --username gitlab-ci-token \
    --password "$CI_JOB_TOKEN"
fi
