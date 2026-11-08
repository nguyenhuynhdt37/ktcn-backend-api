#!/usr/bin/env bash
set -euo pipefail
# Invoked by a root-owned wrapper outside the writable runner directory.
component=${1:?Expected runner component}
case "$component" in
  backend) repo=ktcn-backend-api; workflow=deploy.yml ;;
  frontend) repo=ktcn-client-frontend; workflow=ci.yml ;;
  admin) repo=ktcn-admin-portal; workflow=deploy.yml ;;
  *) echo 'Unknown runner component'; exit 1 ;;
esac
expected="nguyenhuynhdt37/$repo"
[[ ${GITHUB_REPOSITORY-} == "$expected" ]] || { echo 'Runner repository rejected'; exit 1; }
[[ ${GITHUB_REF-} == refs/heads/main ]] || { echo 'Runner accepts main only'; exit 1; }
case "${GITHUB_EVENT_NAME-}" in
  push|workflow_dispatch) ;;
  *) echo 'Runner rejects pull requests and other event types'; exit 1 ;;
esac
case "${GITHUB_WORKFLOW_REF-}:${GITHUB_JOB-}" in
  "$expected/.github/workflows/$workflow@refs/heads/main:deploy-test"|\
  "$expected/.github/workflows/$workflow@refs/heads/main:deploy-production") ;;
  'nguyenhuynhdt37/ktcn-backend-api/.github/workflows/promote.yml@refs/heads/main:deploy')
    [[ $component == backend && ${GITHUB_EVENT_NAME-} == workflow_dispatch ]] || exit 1 ;;
  *) echo 'Runner rejects this workflow or job'; exit 1 ;;
esac
echo 'Runner guard accepted trusted main deployment job.'
