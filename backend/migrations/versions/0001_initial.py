"""initial schema: enums, 4 tables, constraints, indexes

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

# create_type=False — the types are created explicitly in upgrade() so the
# columns reference the existing native enum types.
SYNC_ESTADO = postgresql.ENUM(
    "pending", "running", "completed", "failed", "rejected", name="sync_estado", create_type=False
)
TIPO_ARCHIVO = postgresql.ENUM("ventas", "inventario", "clientes", name="tipo_archivo", create_type=False)
ARCHIVO_ESTADO = postgresql.ENUM("accepted", "rejected", name="archivo_estado", create_type=False)
NIVEL_ERROR = postgresql.ENUM("WARNING", "ERROR", "CRITICAL", name="nivel_error", create_type=False)
RESULTADO = postgresql.ENUM("success", "failed", name="resultado", create_type=False)


def upgrade() -> None:
    # --- enums -----------------------------------------------------------------
    op.execute("CREATE TYPE sync_estado AS ENUM ('pending', 'running', 'completed', 'failed', 'rejected')")
    op.execute("CREATE TYPE tipo_archivo AS ENUM ('ventas', 'inventario', 'clientes')")
    op.execute("CREATE TYPE archivo_estado AS ENUM ('accepted', 'rejected')")
    op.execute("CREATE TYPE nivel_error AS ENUM ('WARNING', 'ERROR', 'CRITICAL')")
    op.execute("CREATE TYPE resultado AS ENUM ('success', 'failed')")

    # --- sincronizaciones ------------------------------------------------------
    op.create_table(
        "sincronizaciones",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fecha_ejecucion", sa.Date(), nullable=False),
        sa.Column("estado", SYNC_ESTADO, server_default=sa.text("'pending'"), nullable=False),
        sa.Column("iniciado_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalizado_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usuario_origen", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_sincronizaciones"),
    )
    op.create_index("ix_sincronizaciones_correlation_id", "sincronizaciones", ["correlation_id"], unique=True)
    op.create_index("ix_sincronizaciones_estado", "sincronizaciones", ["estado"])
    op.create_index("ix_sincronizaciones_fecha_ejecucion", "sincronizaciones", ["fecha_ejecucion"])
    op.create_index("ix_sincronizaciones_estado_fecha_ejecucion", "sincronizaciones", ["estado", "fecha_ejecucion"])

    # --- archivos_procesados ---------------------------------------------------
    op.create_table(
        "archivos_procesados",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sincronizacion_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("nombre_archivo", sa.String(length=255), nullable=False),
        sa.Column("tipo_archivo", TIPO_ARCHIVO, nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("estado", ARCHIVO_ESTADO, nullable=False),
        sa.Column("registros_totales", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("datos_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(
            ["sincronizacion_id"],
            ["sincronizaciones.id"],
            name="fk_archivos_procesados_sincronizacion_id_sincronizaciones",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_archivos_procesados"),
    )
    op.create_index("ix_archivos_procesados_checksum", "archivos_procesados", ["checksum"], unique=True)
    op.create_index("ix_archivos_procesados_sincronizacion_id", "archivos_procesados", ["sincronizacion_id"])
    op.create_index("ix_archivos_procesados_estado", "archivos_procesados", ["estado"])
    op.create_index("ix_archivos_procesados_sincronizacion_id_estado", "archivos_procesados", ["sincronizacion_id", "estado"])

    # --- logs_errores ----------------------------------------------------------
    op.create_table(
        "logs_errores",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("servicio_responsable", sa.String(length=100), nullable=False),
        sa.Column("nivel_error", NIVEL_ERROR, nullable=False),
        sa.Column("codigo_error", sa.String(length=50), nullable=False),
        sa.Column("mensaje", sa.Text(), nullable=False),
        sa.Column("stack_trace", sa.Text(), nullable=True),
        sa.Column("creado_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["correlation_id"],
            ["sincronizaciones.correlation_id"],
            name="fk_logs_errores_correlation_id_sincronizaciones",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_logs_errores"),
    )
    op.create_index("ix_logs_errores_correlation_id", "logs_errores", ["correlation_id"])
    op.create_index(
        "ix_logs_errores_correlation_id_creado_at",
        "logs_errores",
        ["correlation_id", sa.text("creado_at DESC")],
    )

    # --- acciones_remediacion --------------------------------------------------
    op.create_table(
        "acciones_remediacion",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sincronizacion_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("accion_ejecutada", sa.String(length=100), nullable=False),
        sa.Column("ejecutado_por", sa.String(length=100), nullable=False),
        sa.Column("resultado", RESULTADO, nullable=False),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("ejecutada_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["sincronizacion_id"],
            ["sincronizaciones.id"],
            name="fk_acciones_remediacion_sincronizacion_id_sincronizaciones",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_acciones_remediacion"),
    )
    op.create_index("ix_acciones_remediacion_sincronizacion_id", "acciones_remediacion", ["sincronizacion_id"])
    op.create_index("ix_acciones_remediacion_ejecutada_at", "acciones_remediacion", ["ejecutada_at"])
    op.create_index(
        "ix_acciones_remediacion_sincronizacion_id_ejecutada_at",
        "acciones_remediacion",
        ["sincronizacion_id", "ejecutada_at"],
    )


def downgrade() -> None:
    op.drop_table("acciones_remediacion")
    op.drop_table("logs_errores")
    op.drop_table("archivos_procesados")
    op.drop_table("sincronizaciones")
    op.execute("DROP TYPE resultado")
    op.execute("DROP TYPE nivel_error")
    op.execute("DROP TYPE archivo_estado")
    op.execute("DROP TYPE tipo_archivo")
    op.execute("DROP TYPE sync_estado")
