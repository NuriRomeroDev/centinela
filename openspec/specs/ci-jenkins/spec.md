# CI Jenkins Specification

## Purpose

Declarative Jenkins pipeline for the technical test: checkout, lint, unit tests with an 80% coverage gate, and docker build. No deploy/publish stage in scope.

## Requirements

### Requirement 1: Declarative pipeline

The repo root MUST contain a declarative `Jenkinsfile` with `pipeline { agent any; stages { ... } }` and the stages in order: checkout, lint, unit tests, docker build. Any stage failure MUST fail the build. No hard-coded credentials MUST appear in the file.

#### Scenario: Stage order

- GIVEN a fresh Jenkins job on this repo
- WHEN the build runs
- THEN the stage view shows checkout -> lint -> unit tests -> docker build in order

### Requirement 2: Checkout stage

The checkout stage MUST obtain the source from SCM into the workspace (e.g. checkout scm).

#### Scenario: Fresh workspace

- GIVEN an empty workspace
- WHEN the checkout stage runs
- THEN the repository source is present at the expected revision

### Requirement 3: Lint stage

The lint stage MUST run backend linting (flake8 and black --check per pyproject config) and frontend linting (eslint per eslint.config.js). Lint violations MUST fail the stage.

#### Scenario: Lint gate

- GIVEN a change that violates black formatting
- WHEN the lint stage runs
- THEN the build fails with the black diff reported

### Requirement 4: Unit tests stage

The unit tests stage MUST run backend `pytest --cov --cov-fail-under=80` and frontend `vitest run --coverage` (80% threshold, per openspec config). Either suite failing or coverage below 80% MUST fail the build. Tests MUST run hermetically (e.g. containerized or isolated environment).

#### Scenario: Coverage failure

- GIVEN backend coverage at 78%
- WHEN the unit tests stage runs
- THEN the build fails and reports the coverage gap

### Requirement 5: Docker build stage

The docker build stage MUST build the backend and frontend images (docker compose build or explicit docker build). It MUST succeed without publish/push (out of scope).

#### Scenario: Image build

- GIVEN successful prior stages
- WHEN the docker build stage runs
- THEN both images build successfully and no push or deploy occurs

### Requirement 6: Pipeline hygiene

The Jenkinsfile MUST be valid declarative syntax, must not use deprecated steps, and MUST fail fast. A post { failure } block MAY notify (email/slack) but MUST NOT be required. No secrets in the file.

#### Scenario: Syntax validity

- GIVEN the Jenkinsfile
- WHEN parsed by Jenkins
- THEN it loads without errors and all stages are discoverable

## Acceptance Criteria

- Jenkinsfile: 4 stages in order, declarative, no secrets
- Lint stage gates on flake8 + black --check + eslint
- Unit tests gate on pytest --cov-fail-under=80 and vitest 80% coverage
- Docker build stage succeeds (backend + frontend images) with no deploy
