"""
Modelos para el Historial de Postulaciones y Registro en Base de Datos
"""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ApplicationStatus(str, Enum):
    ANALYZED = "analyzed"
    CHANGES_REQUESTED = "changes_requested"
    PDF_GENERATED = "pdf_generated"
    DRAFT_CREATED = "draft_created"
    DISCARDED = "discarded"
    SENT_MANUALLY = "sent_manually"


class ApplicationRecord(BaseModel):
    """Registro de base de datos para una postulación."""
    id: Optional[int] = Field(default=None, description="ID autoincremental de la base de datos")
    vacancy_title: str
    company_name: str
    vacancy_url: Optional[str] = None
    match_percentage: int
    base_cv_used: str
    pdf_filename: Optional[str] = None
    pdf_path: Optional[str] = None
    email_draft_id: Optional[str] = None
    recruiter_email: Optional[str] = None
    status: ApplicationStatus = ApplicationStatus.ANALYZED
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
