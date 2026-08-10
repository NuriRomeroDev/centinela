# OpenSpec — centinela

Spec-driven development artifacts for the **centinela** project (banking reconciliation & idempotency control platform).

## Layout

```
openspec/
├── config.yaml              <- Project-specific SDD config (context, testing, phase rules)
├── specs/                   <- Source of truth (main specs)
│   └── {domain}/spec.md
└── changes/                 <- Active changes
    ├── archive/             <- Completed changes (YYYY-MM-DD-{change-name}/)
    └── {change-name}/       <- Active change folder
        ├── state.yaml       <- DAG state (survives compaction)
        ├── exploration.md   <- (optional) from sdd-explore
        ├── proposal.md      <- from sdd-propose
        ├── specs/{domain}/spec.md   <- Delta spec from sdd-spec
        ├── design.md        <- from sdd-design
        ├── tasks.md         <- from sdd-tasks (updated by sdd-apply)
        └── verify-report.md <- from sdd-verify
```

## Phase Flow

Start a change with `/sdd-explore` or `/sdd-new`, then proceed through
propose → spec → design → tasks → apply → verify → archive.
