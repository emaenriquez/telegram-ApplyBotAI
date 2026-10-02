"""
Modelos de Dominio para Vacantes de Empleo
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class JobPosting(BaseModel):
    """Representa los datos estructurados extraídos de una vacante de empleo."""
    title: str = Field(description="Título del puesto de trabajo")
    company: str = Field(description="Nombre de la empresa")
    location: Optional[str] = Field(default="No especificada", description="Ubicación geográfica")
    workplace_type: Optional[str] = Field(default="Remoto / No especificado", description="Remoto, Híbrido o Presencial")
    url: Optional[str] = Field(default=None, description="URL original de la publicación")
    description_raw: str = Field(description="Texto completo sin procesar de la vacante")
    responsibilities: List[str] = Field(default_factory=list, description="Lista de responsabilidades principales")
    required_skills: List[str] = Field(default_factory=list, description="Habilidades y tecnologías obligatorias")
    desirable_skills: List[str] = Field(default_factory=list, description="Habilidades y tecnologías deseables")
    recruiter_email: Optional[str] = Field(default=None, description="Correo electrónico del reclutador si existe")
    recruiter_name: Optional[str] = Field(default=None, description="Nombre del reclutador o contacto")
    required_email_subject: Optional[str] = Field(default=None, description="Asunto exacto que la vacante exige usar en el correo de postulación")
    language: str = Field(default="es", description="Idioma principal de la vacante (es, en, etc.)")


class MatchScoreResult(BaseModel):
    """Resultado del análisis de compatibilidad (ATS Fit Score)."""
    match_percentage: int = Field(ge=0, le=100, description="Porcentaje de compatibilidad de 0 a 100")
    recommended_cv_base: str = Field(description="Nombre del archivo CV base recomendado (ej: cv_backend_python.json)")
    matching_skills: List[str] = Field(default_factory=list, description="Habilidades del candidato requeridas por el puesto")
    missing_skills: List[str] = Field(default_factory=list, description="Habilidades requeridas que faltan en el perfil")
    strengths_summary: str = Field(description="Resumen de puntos fuertes del candidato para este rol")
    advice: List[str] = Field(default_factory=list, description="Consejos para destacar en la postulación")
