"""Add pg_trgm extension and GIN indexes on logs_errores for fast ILIKE search

Revision ID: 0002_trigram_indexes
Revises: 0001_initial
Create Date: 2026-08-10
"""

from alembic import op

revision = "0002_trigram_indexes"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.execute(
        "CREATE INDEX ix_logs_errores_codigo_trgm "
        "ON logs_errores USING GIN (codigo_error gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_logs_errores_mensaje_trgm "
        "ON logs_errores USING GIN (mensaje gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_logs_errores_servicio_trgm "
        "ON logs_errores USING GIN (servicio_responsable gin_trgm_ops)"
    )

    op.create_index("ix_logs_errores_nivel_error", "logs_errores", ["nivel_error"])
    op.create_index(
        "ix_logs_errores_creado_at_desc",
        "logs_errores",
        ["creado_at"],
        postgresql_ops={"creado_at": "DESC"},
    )


def downgrade() -> None:
    op.drop_index("ix_logs_errores_creado_at_desc", table_name="logs_errores")
    op.drop_index("ix_logs_errores_nivel_error", table_name="logs_errores")
    op.execute("DROP INDEX IF EXISTS ix_logs_errores_servicio_trgm")
    op.execute("DROP INDEX IF EXISTS ix_logs_errores_mensaje_trgm")
    op.execute("DROP INDEX IF EXISTS ix_logs_errores_codigo_trgm")
