"""
Puertos / Interfaces Abstractas para la Arquitectura Limpia
"""
from typing import Protocol, List, Optional
from core.models.vacancy import JobPosting, MatchScoreResult
from core.models.profile import UserProfile
from core.models.tailored_cv import TailoredCV, EmailDraftProposal
from core.models.application import ApplicationRecord


class ScraperPort(Protocol):
    """Puerto para la extracción de ofertas laborales."""
    async def extract_from_url(self, url: str) -> JobPosting:
        ...

    async def extract_from_raw_text(self, text: str, source_url: Optional[str] = None) -> JobPosting:
        ...


class LLMPort(Protocol):
    """Puerto para operaciones con Modelos de Lenguaje (Gemini)."""
    async def parse_vacancy_text(self, text: str) -> JobPosting:
        ...

    async def analyze_match(self, vacancy: JobPosting, base_profiles: List[UserProfile]) -> MatchScoreResult:
        ...

    async def tailor_cv(
        self,
        vacancy: JobPosting,
        base_profile: UserProfile,
        user_feedback: Optional[str] = None
    ) -> TailoredCV:
        ...

    async def generate_email_draft(
        self,
        vacancy: JobPosting,
        tailored_cv: TailoredCV
    ) -> EmailDraftProposal:
        ...


class PDFPort(Protocol):
    """Puerto para generación de PDFs a partir de plantillas."""
    async def render_cv_to_pdf(
        self,
        cv: TailoredCV,
        output_filename: str,
        template_name: str = "modern_ats"
    ) -> str:
        ...


class EmailPort(Protocol):
    """Puerto para gestión de correo electrónico (creación de borradores)."""
    async def create_draft(
        self,
        recipient: Optional[str],
        subject: str,
        body: str,
        attachment_path: Optional[str] = None
    ) -> str:
        ...


class StoragePort(Protocol):
    """Puerto para persistencia de datos (base de datos local)."""
    async def init_db(self) -> None:
        ...

    async def save_application(self, record: ApplicationRecord) -> int:
        ...

    async def update_status(self, application_id: int, status: str, draft_id: Optional[str] = None) -> None:
        ...

    async def get_recent_applications(self, limit: int = 10) -> List[ApplicationRecord]:
        ...
