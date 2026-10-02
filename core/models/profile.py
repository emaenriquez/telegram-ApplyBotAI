"""
Modelos de Dominio para el Perfil Profesional del Usuario (CV Base)
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class WorkExperience(BaseModel):
    """Representa un cargo o experiencia laboral."""
    role: str = Field(description="Título del puesto desempeñado")
    company: str = Field(description="Nombre de la empresa")
    location: Optional[str] = Field(default=None, description="Ubicación o modalidad")
    start_date: str = Field(description="Fecha de inicio (ej: Enero 2021)")
    end_date: str = Field(default="Presente", description="Fecha de fin o Presente")
    achievements: List[str] = Field(
        default_factory=list,
        description="Viñetas con logros concretos y cuantificables"
    )
    technologies: List[str] = Field(default_factory=list, description="Stack técnico utilizado en este rol")


class Education(BaseModel):
    """Representa estudios académicos o certificaciones de alto impacto."""
    degree: str = Field(description="Grado obtenido o título del curso/carrera")
    institution: str = Field(description="Universidad o institución emisora")
    year: str = Field(description="Año o rango de fechas de graduación")
    details: Optional[str] = Field(default=None, description="Menciones de honor o detalles clave")


class Project(BaseModel):
    """Representa proyectos relevantes de software o portafolio."""
    name: str = Field(description="Nombre del proyecto")
    description: str = Field(description="Descripción concisa del proyecto y su impacto")
    technologies: List[str] = Field(default_factory=list, description="Tecnologías clave empleadas")
    url: Optional[str] = Field(default=None, description="Enlace a GitHub o demo online")


class UserProfile(BaseModel):
    """Perfil completo del usuario que alimenta la generación del CV."""
    id: str = Field(description="Identificador del perfil (ej: backend_python, fullstack)")
    full_name: str = Field(description="Nombre y apellidos del usuario")
    headline: str = Field(description="Titular profesional (ej: Senior Python / Backend Developer)")
    email: str = Field(description="Correo electrónico de contacto")
    phone: Optional[str] = Field(default=None, description="Número de teléfono")
    location: Optional[str] = Field(default=None, description="Ciudad, País")
    linkedin_url: Optional[str] = Field(default=None, description="Enlace a perfil de LinkedIn")
    github_url: Optional[str] = Field(default=None, description="Enlace a GitHub o portafolio")
    portfolio_url: Optional[str] = Field(default=None, description="Sitio web personal")
    
    summary: str = Field(description="Resumen profesional o extracto inicial")
    skills: List[str] = Field(default_factory=list, description="Lista de habilidades técnicas y blandas")
    experience: List[WorkExperience] = Field(default_factory=list, description="Historial laboral")
    projects: List[Project] = Field(default_factory=list, description="Proyectos destacados")
    education: List[Education] = Field(default_factory=list, description="Educación y títulos")
    languages: List[str] = Field(default_factory=list, description="Idiomas y nivel de dominio")
