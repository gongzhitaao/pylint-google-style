#!/usr/bin/env bash
# Publish to one or more PyPI registries when no package exists on the
# registry yet, or when the minor/major version has been bumped.
#
# Targets are selected via PUBLISH_TARGETS (comma-separated).  Supported
# values: "gitlab", "gcp".  Defaults to "gitlab".
set -euo pipefail

TARGETS="${PUBLISH_TARGETS:-gitlab}"

declare -a TARGET_LIST=()
IFS=',' read -ra _raw <<< "$TARGETS"
for t in "${_raw[@]}"; do
  TARGET_LIST+=("${t// /}")
done

contains_target() {
  local needle="$1"
  for t in "${TARGET_LIST[@]}"; do
    [ "$t" = "$needle" ] && return 0
  done
  return 1
}

authenticate_gcp() {
  if [ -n "${PYLINT_GOOGLE_STYLE_CI_DEPLOYER_B64_JSON:-}" ]; then
    local key_file
    key_file="$(mktemp)"
    echo "$PYLINT_GOOGLE_STYLE_CI_DEPLOYER_B64_JSON" | base64 -d > "$key_file"
    gcloud auth activate-service-account --key-file="$key_file"
    rm -f "$key_file"
  fi
  gcloud config set project "$GCP_AR_PROJECT"
}

publish_gitlab() {
  uv publish \
    --publish-url "${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/packages/pypi" \
    --username gitlab-ci-token \
    --password "$CI_JOB_TOKEN"
}

publish_gcp() {
  local token
  token="$(gcloud auth print-access-token)"
  uv publish \
    --publish-url "https://${GCP_LOCATION}-python.pkg.dev/${GCP_AR_PROJECT}/${GCP_REPO}/" \
    --username oauth2accesstoken \
    --password "$token"
}

# Authenticate to GCP before should_publish.py queries Artifact Registry.
if contains_target gcp; then
  authenticate_gcp
fi

declare -a publish_to=()
for target in "${TARGET_LIST[@]}"; do
  if python .gitlab/ci/should_publish.py --target="$target"; then
    publish_to+=("$target")
  fi
done

if [ ${#publish_to[@]} -eq 0 ]; then
  echo "No targets need publishing."
  exit 0
fi

uv build

for target in "${publish_to[@]}"; do
  case "$target" in
    gitlab) publish_gitlab ;;
    gcp) publish_gcp ;;
    *) echo "Unknown target: $target" >&2; exit 1 ;;
  esac
done
