"""
Adaptador para Google Gemini AI
Maneja la extracción, análisis de compatibilidad, adaptación de CV y generación de emails.
"""
import asyncio
import json
import logging
from typing import List, Optional
from config.settings import settings
from config.prompts import (
    VACANCY_EXTRACTION_PROMPT,
    ATS_MATCH_ANALYSIS_PROMPT,
    CV_TAILORING_PROMPT,
    EMAIL_COVER_LETTER_PROMPT
)
from core.models.vacancy import JobPosting, MatchScoreResult
from core.models.profile import UserProfile
from core.models.tailored_cv import TailoredCV, EmailDraftProposal

logger = logging.getLogger(__name__)

# Configuración de reintentos
MAX_RETRIES = 3
RETRY_DELAYS = [5, 15, 30]  # segundos de espera entre reintentos


class GeminiAdapter:
    """Implementación del puerto LLMPort usando Google Gemini."""

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model_name or settings.GEMINI_MODEL
        self._client = None
        self._init_client()

    def _init_client(self):
        """Inicializa el cliente de Gemini según la librería disponible."""
        if not self.api_key:
            logger.warning("GEMINI_API_KEY no está configurada en .env")
            return

        try:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
            self._is_new_sdk = True
            logger.info(f"Cliente Gemini inicializado con google-genai SDK ({self.model_name})")
        except ImportError:
            try:
                import google.generativeai as legacy_genai
                legacy_genai.configure(api_key=self.api_key)
                self._client = legacy_genai.GenerativeModel(self.model_name)
                self._is_new_sdk = False
                logger.info(f"Cliente Gemini inicializado con google-generativeai SDK ({self.model_name})")
            except ImportError:
                logger.error("No se encontró ninguna librería de Gemini instalada.")

    def _ensure_ready(self):
        if not self.api_key:
            raise ValueError(
                "La clave GEMINI_API_KEY está vacía en el archivo .env. "
                "Por favor, coloca tu clave de Google AI Studio para usar la IA."
            )
        if not self._client:
            self._init_client()
            if not self._client:
                raise RuntimeError("No se pudo inicializar el cliente de Gemini.")

    def _is_retryable_error(self, error: Exception) -> bool:
        """Determina si el error de Gemini es temporal y vale la pena reintentar."""
        error_str = str(error).lower()
        retryable_codes = ["503", "429", "unavailable", "resource_exhausted", "overloaded", "high demand"]
        return any(code in error_str for code in retryable_codes)

    async def _call_gemini_json(self, system_instruction: str, user_prompt: str) -> dict:
        """Invoca a Gemini con reintentos automáticos ante errores 503/429."""
        self._ensure_ready()
        prompt_completo = f"{system_instruction}\n\nDatos de entrada:\n{user_prompt}\n\nResponde únicamente con un objeto JSON sin markdown backticks."

        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                if getattr(self, "_is_new_sdk", False):
                    response = self._client.models.generate_content(
                        model=self.model_name,
                        contents=prompt_completo,
                        config={"response_mime_type": "application/json"}
                    )
                    text = response.text
                else:
                    response = await self._client.generate_content_async(
                        prompt_completo,
                        generation_config={"response_mime_type": "application/json"}
                    )
                    text = response.text

                # Limpiar posibles delimitadores markdown
                clean_text = text.strip()
                if clean_text.startswith("```json"):
                    clean_text = clean_text[7:]
                if clean_text.startswith("```"):
                    clean_text = clean_text[3:]
                if clean_text.endswith("```"):
                    clean_text = clean_text[:-3]
                clean_text = clean_text.strip()

                return json.loads(clean_text)

            except Exception as e:
                last_error = e
                if self._is_retryable_error(e) and attempt < MAX_RETRIES:
                    delay = RETRY_DELAYS[attempt]
                    logger.warning(
                        f"Gemini no disponible (intento {attempt + 1}/{MAX_RETRIES + 1}). "
                        f"Reintentando en {delay}s... Error: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Error en llamada a Gemini (intento {attempt + 1}): {e}")
                    raise

    async def parse_vacancy_text(self, text: str, source_url: Optional[str] = None) -> JobPosting:
        """Extrae la información estructurada de una vacante a partir de texto libre o HTML."""
        data = await self._call_gemini_json(
            system_instruction=VACANCY_EXTRACTION_PROMPT,
            user_prompt=text
        )
        if source_url and not data.get("url"):
            data["url"] = source_url
        if not data.get("description_raw"):
            data["description_raw"] = text[:2000]

        # Gemini a veces devuelve null en campos obligatorios; evitar fallo de validación
        for field in ("title", "company"):
            if data.get(field) is None:
                data[field] = ""

        return JobPosting(**data)

    async def analyze_match(self, vacancy: JobPosting, base_profiles: List[UserProfile]) -> MatchScoreResult:
        """Analiza la vacante contra la lista de perfiles disponibles y calcula el match score."""
        profiles_summary = [
            {
                "id": p.id,
                "headline": p.headline,
                "skills": p.skills,
                "summary": p.summary,
                "experience_count": len(p.experience)
            }
            for p in base_profiles
        ]

        input_data = {
            "vacancy": {
                "title": vacancy.title,
                "company": vacancy.company,
                "required_skills": vacancy.required_skills,
                "desirable_skills": vacancy.desirable_skills,
                "responsibilities": vacancy.responsibilities,
                "description": vacancy.description_raw[:2500]
            },
            "candidate_profiles": profiles_summary
        }

        data = await self._call_gemini_json(
            system_instruction=ATS_MATCH_ANALYSIS_PROMPT,
            user_prompt=json.dumps(input_data, ensure_ascii=False)
        )

        return MatchScoreResult(**data)

    async def tailor_cv(
        self,
        vacancy: JobPosting,
        base_profile: UserProfile,
        user_feedback: Optional[str] = None
    ) -> TailoredCV:
        """Adapta el CV base seleccionado a la vacante específica."""
        input_data = {
            "vacancy": {
                "title": vacancy.title,
                "company": vacancy.company,
                "required_skills": vacancy.required_skills,
                "desirable_skills": vacancy.desirable_skills,
                "responsibilities": vacancy.responsibilities
            },
            "base_cv": base_profile.model_dump(),
            "user_custom_feedback": user_feedback or "Ninguno. Aplica las mejores prácticas de adaptación ATS."
        }

        data = await self._call_gemini_json(
            system_instruction=CV_TAILORING_PROMPT,
            user_prompt=json.dumps(input_data, ensure_ascii=False)
        )

        return TailoredCV(**data)

    async def generate_email_draft(
        self,
        vacancy: JobPosting,
        tailored_cv: TailoredCV
    ) -> EmailDraftProposal:
        """Genera un asunto y cuerpo de correo profesional con la postulación."""
        input_data = {
            "candidate_name": tailored_cv.full_name,
            "candidate_headline": tailored_cv.headline,
            "candidate_email": tailored_cv.email,
            "vacancy_title": vacancy.title,
            "company": vacancy.company,
            "recruiter_email": vacancy.recruiter_email,
            "recruiter_name": vacancy.recruiter_name,
            "top_skills": tailored_cv.highlighted_skills[:6]
        }

        data = await self._call_gemini_json(
            system_instruction=EMAIL_COVER_LETTER_PROMPT,
            user_prompt=json.dumps(input_data, ensure_ascii=False)
        )

        return EmailDraftProposal(**data)
