"""
Adaptador de Base de Datos SQLite Asíncrono
Gestiona el historial de postulaciones, estados y archivos generados.
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import aiosqlite
from config.settings import settings
from core.models.application import ApplicationRecord, ApplicationStatus

logger = logging.getLogger(__name__)


class SQLiteStorageAdapter:
    """Implementación de StoragePort con SQLite asíncrono."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.DATABASE_PATH
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    async def init_db(self) -> None:
        """Crea las tablas necesarias si no existen."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vacancy_title TEXT NOT NULL,
                    company_name TEXT NOT NULL,
                    vacancy_url TEXT,
                    match_percentage INTEGER NOT NULL,
                    base_cv_used TEXT NOT NULL,
                    pdf_filename TEXT,
                    pdf_path TEXT,
                    email_draft_id TEXT,
                    recruiter_email TEXT,
                    status TEXT NOT NULL,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            await db.commit()
            logger.info("Base de datos SQLite inicializada correctamente.")

    async def save_application(self, record: ApplicationRecord) -> int:
        """Inserta una nueva postulación y retorna su ID."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO applications (
                    vacancy_title, company_name, vacancy_url, match_percentage,
                    base_cv_used, pdf_filename, pdf_path, email_draft_id,
                    recruiter_email, status, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.vacancy_title,
                record.company_name,
                record.vacancy_url,
                record.match_percentage,
                record.base_cv_used,
                record.pdf_filename,
                record.pdf_path,
                record.email_draft_id,
                record.recruiter_email,
                record.status.value if isinstance(record.status, ApplicationStatus) else str(record.status),
                record.notes,
                record.created_at.isoformat(),
                record.updated_at.isoformat()
            ))
            await db.commit()
            record_id = cursor.lastrowid
            logger.info(f"Postulación guardada en BD con ID: {record_id}")
            return record_id

    async def update_status(
        self,
        application_id: int,
        status: ApplicationStatus,
        draft_id: Optional[str] = None,
        pdf_path: Optional[str] = None
    ) -> None:
        """Actualiza el estado y metadatos de una postulación existente."""
        async with aiosqlite.connect(self.db_path) as db:
            query = "UPDATE applications SET status = ?, updated_at = ?"
            params = [status.value if isinstance(status, ApplicationStatus) else str(status), datetime.utcnow().isoformat()]

            if draft_id is not None:
                query += ", email_draft_id = ?"
                params.append(draft_id)

            if pdf_path is not None:
                query += ", pdf_path = ?, pdf_filename = ?"
                params.append(pdf_path)
                params.append(Path(pdf_path).name)

            query += " WHERE id = ?"
            params.append(application_id)

            await db.execute(query, tuple(params))
            await db.commit()
            logger.info(f"Postulación {application_id} actualizada a estado: {status}")

    async def get_recent_applications(self, limit: int = 10) -> List[ApplicationRecord]:
        """Obtiene las postulaciones más recientes."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM applications ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            rows = await cursor.fetchall()
            results = []
            for row in rows:
                results.append(ApplicationRecord(
                    id=row["id"],
                    vacancy_title=row["vacancy_title"],
                    company_name=row["company_name"],
                    vacancy_url=row["vacancy_url"],
                    match_percentage=row["match_percentage"],
                    base_cv_used=row["base_cv_used"],
                    pdf_filename=row["pdf_filename"],
                    pdf_path=row["pdf_path"],
                    email_draft_id=row["email_draft_id"],
                    recruiter_email=row["recruiter_email"],
                    status=ApplicationStatus(row["status"]),
                    notes=row["notes"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"])
                ))
            return results
