#!/usr/bin/env bash
set -euo pipefail
component=${1:?Expected runner component}
case "$component" in
  backend) repo=ktcn-backend-api; workflow=deploy.yml ;;
  frontend) repo=ktcn-client-frontend; workflow=ci.yml ;;
  admin) repo=ktcn-admin-portal; workflow=deploy.yml ;;
  *) echo 'Unknown runner component'; exit 1 ;;
esac
expected="nguyenhuynhdt37/$repo"
[[ ${GITHUB_REPOSITORY-} == "$expected" ]] || { echo 'Runner repository rejected'; exit 1; }
case "${GITHUB_EVENT_NAME-}" in
  push|workflow_dispatch) ;;
  *) echo 'Runner rejects pull requests and other event types'; exit 1 ;;
esac
case "${GITHUB_REF-}:${GITHUB_JOB-}" in
  refs/heads/dev:deploy-test) branch=dev ;;
  refs/heads/main:deploy-production) branch=main ;;
  *) echo 'Runner rejects branch/job mismatch'; exit 1 ;;
esac
[[ ${GITHUB_WORKFLOW_REF-} == "$expected/.github/workflows/$workflow@refs/heads/$branch" ]] || { echo 'Runner workflow rejected'; exit 1; }
echo "Runner guard accepted $branch deployment job."
