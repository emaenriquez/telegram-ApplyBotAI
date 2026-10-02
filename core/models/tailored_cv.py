"""
Modelos para el CV Adaptado y Propuesta de Postulación
"""
from typing import List, Optional
from pydantic import BaseModel, Field
from core.models.profile import WorkExperience, Education, Project


class TailoredCV(BaseModel):
    """Currículum vitae adaptado para una vacante específica."""
    full_name: str
    headline: str = Field(description="Titular adaptado a la vacante")
    email: str
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None

    summary: str = Field(description="Extracto profesional adaptado con keywords de la vacante")
    highlighted_skills: List[str] = Field(description="Habilidades priorizadas según la vacante")
    experience: List[WorkExperience] = Field(description="Experiencia con viñetas reordenadas y enfocadas")
    projects: List[Project] = Field(default_factory=list, description="Proyectos más relevantes para el puesto")
    education: List[Education] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)

    # Metadatos del proceso
    tailoring_rationale: str = Field(
        description="Explicación de qué cambios se realizaron y por qué aumentan la compatibilidad"
    )


class EmailDraftProposal(BaseModel):
    """Propuesta de correo de postulación generado para el borrador."""
    subject: str = Field(description="Asunto del correo electrónico")
    body: str = Field(description="Cuerpo del mensaje en texto o HTML ligero")
    recipient: Optional[str] = Field(default=None, description="Destinatario sugerido o placeholder")
