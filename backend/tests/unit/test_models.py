"""ORM model metadata tests (T1.5). No DB — pure SQLAlchemy introspection.

RED phase: references ``app.models.*`` which do not exist yet.
"""

from sqlalchemy import Date, DateTime, Enum as SAEnum, Integer, Uuid
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base
from app.models import (
    AccionRemediacion,
    ArchivoProcesado,
    LogError,
    Sincronizacion,
)
from app.models.enums import (
    ArchivoEstado,
    NivelError,
    Resultado,
    SyncEstado,
    TipoArchivo,
)

MODELS = {
    "sincronizaciones": Sincronizacion,
    "archivos_procesados": ArchivoProcesado,
    "logs_errores": LogError,
    "acciones_remediacion": AccionRemediacion,
}


# --- table registry ----------------------------------------------------------


def test_all_four_tables_registered_on_base_metadata():
    names = set(Base.metadata.tables.keys())
    assert set(MODELS.keys()) <= names


# --- sincronizaciones (data-model Req 1) ------------------------------------


def test_sincronizaciones_columns():
    t = Sincronizacion.__table__
    assert set(t.columns.keys()) == {
        "id",
        "correlation_id",
        "fecha_ejecucion",
        "estado",
        "iniciado_at",
        "finalizado_at",
        "usuario_origen",
    }
    assert isinstance(t.c.id.type, Uuid)
    assert t.c.id.primary_key is True
    assert t.c.correlation_id.nullable is False
    assert t.c.correlation_id.unique is True
    assert isinstance(t.c.fecha_ejecucion.type, Date)
    assert isinstance(t.c.iniciado_at.type, DateTime) and t.c.iniciado_at.type.timezone is True
    assert t.c.finalizado_at.nullable is True
    assert t.c.usuario_origen.type.length == 100


def test_sincronizaciones_estado_enum():
    col = Sincronizacion.__table__.c.estado
    assert isinstance(col.type, SAEnum)
    assert col.type.enum_class is SyncEstado
    assert col.type.enums == ["pending", "running", "completed", "failed", "rejected"]
    assert col.default.arg == SyncEstado.pending


def test_sincronizaciones_composite_index_and_unique_correlation():
    t = Sincronizacion.__table__
    assert any(idx.unique for idx in t.indexes)  # unique index on correlation_id
    assert any(idx.columns.keys() == ["estado", "fecha_ejecucion"] for idx in t.indexes)
    assert any(idx.columns.keys() == ["estado"] for idx in t.indexes)
    assert any(idx.columns.keys() == ["fecha_ejecucion"] for idx in t.indexes)


# --- archivos_procesados (data-model Req 2) ----------------------------------


def test_archivos_procesados_columns():
    t = ArchivoProcesado.__table__
    assert isinstance(t.c.id.type, Integer)
    assert t.c.id.autoincrement is True
    assert t.c.sincronizacion_id.nullable is False
    assert t.c.nombre_archivo.type.length == 255
    assert t.c.tipo_archivo.type.enum_class is TipoArchivo
    assert t.c.tipo_archivo.type.enums == ["ventas", "inventario", "clientes"]
    assert t.c.estado.type.enum_class is ArchivoEstado
    assert t.c.estado.type.enums == ["accepted", "rejected"]
    assert t.c.checksum.type.length == 64
    assert t.c.checksum.unique is True
    assert isinstance(t.c.datos_payload.type, JSONB)
    assert t.c.datos_payload.nullable is True


def test_archivos_registros_totales_default_zero():
    col = ArchivoProcesado.__table__.c.registros_totales
    assert col.default.arg == 0
    assert col.server_default.arg.text == "0"


def test_archivos_fk_cascade_to_sincronizaciones():
    fk = next(iter(ArchivoProcesado.__table__.c.sincronizacion_id.foreign_keys))
    assert fk.target_fullname == "sincronizaciones.id"
    assert fk.ondelete == "CASCADE"


def test_archivos_composite_index():
    t = ArchivoProcesado.__table__
    assert any(idx.columns.keys() == ["sincronizacion_id", "estado"] for idx in t.indexes)


# --- logs_errores (data-model Req 3) ----------------------------------------


def test_logs_errores_columns():
    t = LogError.__table__
    assert isinstance(t.c.id.type, Integer)
    assert t.c.servicio_responsable.type.length == 100
    assert t.c.nivel_error.type.enum_class is NivelError
    assert t.c.nivel_error.type.enums == ["WARNING", "ERROR", "CRITICAL"]
    assert t.c.codigo_error.type.length == 50
    assert t.c.mensaje.nullable is False
    assert t.c.stack_trace.nullable is True
    assert t.c.creado_at.server_default is not None


def test_logs_fk_targets_sincronizaciones_correlation_id_cascade():
    fk = next(iter(LogError.__table__.c.correlation_id.foreign_keys))
    assert fk.target_fullname == "sincronizaciones.correlation_id"
    assert fk.ondelete == "CASCADE"


def test_logs_desc_composite_index():
    t = LogError.__table__
    desc = [idx for idx in t.indexes if any("DESC" in str(expr) for expr in idx.expressions)]
    assert desc, "missing (correlation_id, creado_at DESC) index"
    assert any("correlation_id" in str(e) for e in desc[0].expressions)


# --- acciones_remediacion (data-model Req 4) --------------------------------


def test_acciones_remediacion_columns():
    t = AccionRemediacion.__table__
    assert isinstance(t.c.id.type, Integer)
    assert t.c.accion_ejecutada.type.length == 100
    assert t.c.ejecutado_por.type.length == 100
    assert t.c.resultado.type.enum_class is Resultado
    assert t.c.resultado.type.enums == ["success", "failed"]
    assert t.c.notas.nullable is True
    assert t.c.ejecutada_at.nullable is False
    assert t.c.ejecutada_at.server_default is not None


def test_acciones_fk_cascade_and_indexes():
    fk = next(iter(AccionRemediacion.__table__.c.sincronizacion_id.foreign_keys))
    assert fk.target_fullname == "sincronizaciones.id"
    assert fk.ondelete == "CASCADE"
    t = AccionRemediacion.__table__
    assert any(idx.columns.keys() == ["sincronizacion_id", "ejecutada_at"] for idx in t.indexes)


# --- relationships -----------------------------------------------------------


def test_relationships_wired():
    sync_rels = Sincronizacion.__mapper__.relationships.keys()
    assert {"archivos", "logs", "acciones"} <= set(sync_rels)
    assert "sincronizacion" in ArchivoProcesado.__mapper__.relationships.keys()
    assert "sincronizacion" in LogError.__mapper__.relationships.keys()
    assert "sincronizacion" in AccionRemediacion.__mapper__.relationships.keys()
