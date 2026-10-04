"""
Servicio Principal de Coordinación y Casos de Uso
Conecta los adaptadores de LLM, Scraper, PDF, Email y Almacenamiento.
"""
import json
import logging
from pathlib import Path
from typing import List, Optional, Tuple
from config.settings import settings
from core.models.vacancy import JobPosting, MatchScoreResult
from core.models.profile import UserProfile
from core.models.tailored_cv import TailoredCV, EmailDraftProposal
from core.models.application import ApplicationRecord, ApplicationStatus
from adapters.llm.gemini_adapter import GeminiAdapter
from adapters.scrapers.linkedin_scraper import LinkedInScraperAdapter
from adapters.pdf.pdf_adapter import PDFAdapter
from adapters.email.gmail_adapter import GmailAdapter
from adapters.storage.sqlite_adapter import SQLiteStorageAdapter

logger = logging.getLogger(__name__)


class ApplicationCoordinatorService:
    """Orquestador central del flujo de postulación asistido por IA."""

    def __init__(
        self,
        llm_adapter: Optional[GeminiAdapter] = None,
        scraper_adapter: Optional[LinkedInScraperAdapter] = None,
        pdf_adapter: Optional[PDFAdapter] = None,
        email_adapter: Optional[GmailAdapter] = None,
        storage_adapter: Optional[SQLiteStorageAdapter] = None
    ):
        self.llm = llm_adapter or GeminiAdapter()
        self.scraper = scraper_adapter or LinkedInScraperAdapter(self.llm)
        self.pdf = pdf_adapter or PDFAdapter()
        self.email = email_adapter or GmailAdapter()
        self.storage = storage_adapter or SQLiteStorageAdapter()

    def load_base_profiles(self) -> List[UserProfile]:
        """Carga todos los perfiles de CV base disponibles en templates/base_cvs/."""
        base_dir = Path(settings.BASE_CVS_DIR)
        profiles = []

        if not base_dir.exists():
            logger.warning(f"Directorio de CVs base no existe: {base_dir}")
            return profiles

        for file_path in base_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    profiles.append(UserProfile(**data))
            except Exception as e:
                logger.error(f"Error cargando perfil {file_path.name}: {e}")

        return profiles

    def get_profile_by_id(self, profile_id: str) -> Optional[UserProfile]:
        """Encuentra un perfil base específico por su ID o nombre de archivo."""
        profiles = self.load_base_profiles()
        for p in profiles:
            if p.id == profile_id or f"{p.id}.json" == profile_id:
                return p
        # Si no encuentra coincidencia exacta, retorna el primero disponible
        return profiles[0] if profiles else None

    async def process_vacancy_input(self, text_or_url: str) -> JobPosting:
        """Determina si la entrada es una URL de LinkedIn o texto directo y la procesa."""
        text_or_url = text_or_url.strip()
        if text_or_url.startswith("http://") or text_or_url.startswith("https://"):
            try:
                return await self.scraper.extract_from_url(text_or_url)
            except Exception as e:
                logger.warning(f"Fallo al extraer de URL directa ({e}). Intentando fallback...")
                raise
        else:
            return await self.scraper.extract_from_raw_text(text_or_url)

    async def analyze_vacancy(self, vacancy: JobPosting) -> Tuple[MatchScoreResult, UserProfile]:
        """Calcula el match de la vacante y selecciona el mejor perfil base."""
        profiles = self.load_base_profiles()
        if not profiles:
            raise FileNotFoundError(
                f"No se encontraron perfiles base en '{settings.BASE_CVS_DIR}'. "
                "Crea al menos un archivo JSON con tu perfil."
            )

        match_result = await self.llm.analyze_match(vacancy, profiles)
        selected_profile = self.get_profile_by_id(match_result.recommended_cv_base)
        if not selected_profile:
            selected_profile = profiles[0]

        return match_result, selected_profile

    async def generate_tailored_cv(
        self,
        vacancy: JobPosting,
        profile: UserProfile,
        user_feedback: Optional[str] = None
    ) -> TailoredCV:
        """Adapta el CV base seleccionado según la vacante y cualquier feedback humano."""
        return await self.llm.tailor_cv(vacancy, profile, user_feedback=user_feedback)

    async def compile_pdf(self, cv: TailoredCV, company_name: str, job_title: str) -> str:
        """Renderiza y compila el CV a PDF profesional."""
        # Sanitizar nombre de archivo: solo ASCII, sin acentos ni caracteres especiales
        import unicodedata
        def _safe_name(text: str) -> str:
            normalized = unicodedata.normalize("NFKD", text)
            ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
            return "".join(c for c in ascii_text if c.isalnum() or c in ("-", "_", " ")).strip().replace(" ", "_")

        safe_name = _safe_name(cv.full_name) or "Candidato"
        safe_company = _safe_name(company_name).lower() or "empresa"
        safe_title = _safe_name(job_title).lower() or "puesto"
        filename = f"CV_{safe_name}_{safe_company}_{safe_title}.pdf"

        return await self.pdf.render_cv_to_pdf(cv, filename)

    async def prepare_email_draft(
        self,
        vacancy: JobPosting,
        cv: TailoredCV,
        pdf_path: str
    ) -> Tuple[EmailDraftProposal, str]:
        """Genera el contenido del correo y lo guarda como borrador en Gmail con el PDF adjunto."""
        email_proposal = await self.llm.generate_email_draft(vacancy, cv)
        recipient = (vacancy.recruiter_email or email_proposal.recipient or "").strip()
        # Solo emails válidos; si no, borrador sin destinatario (Gmail rechaza "To" inválido)
        if not recipient or "@" not in recipient or " " in recipient:
            recipient = None
        email_proposal.recipient = recipient

        # Si la vacante especifica un asunto obligatorio, usarlo en vez del generado por IA
        subject = vacancy.required_email_subject or email_proposal.subject

        draft_id = await self.email.create_draft(
            recipient=recipient,
            subject=subject,
            body=email_proposal.body,
            attachment_path=pdf_path
        )

        # Actualizar la propuesta con el asunto real usado
        email_proposal.subject = subject

        return email_proposal, draft_id

    async def record_application(
        self,
        vacancy: JobPosting,
        match_score: int,
        base_cv_id: str,
        pdf_path: Optional[str] = None,
        draft_id: Optional[str] = None,
        notes: Optional[str] = None
    ) -> int:
        """Guarda la postulación en la base de datos SQLite."""
        record = ApplicationRecord(
            vacancy_title=vacancy.title,
            company_name=vacancy.company,
            vacancy_url=vacancy.url,
            match_percentage=match_score,
            base_cv_used=base_cv_id,
            pdf_path=pdf_path,
            pdf_filename=Path(pdf_path).name if pdf_path else None,
            email_draft_id=draft_id,
            recruiter_email=vacancy.recruiter_email,
            status=ApplicationStatus.DRAFT_CREATED if draft_id else ApplicationStatus.PDF_GENERATED,
            notes=notes
        )
        return await self.storage.save_application(record)
