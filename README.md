# MediScan Gateway

[![CI](https://github.com/olujegs01/mediscan-gateway/actions/workflows/ci-python.yml/badge.svg)](https://github.com/olujegs01/mediscan-gateway/actions/workflows/ci-python.yml)
[![Coverage Status](https://codecov.io/gh/olujegs01/mediscan-gateway/branch/main/graph/badge.svg)](https://codecov.io/gh/olujegs01/mediscan-gateway)

This repository contains the MediScan Gateway backend (FastAPI) and frontend.

Development setup:

- Install dev tools: `make dev-install`
- Install git hooks: `make precommit-install`
- Run linter: `make lint`
- Run tests: `make test`

CI & Coverage:

- GitHub Actions runs lint and tests on PRs and pushes.
- Coverage is uploaded to Codecov for the main branch. If the repo is private, set the `CODECOV_TOKEN` secret in the repository settings.

