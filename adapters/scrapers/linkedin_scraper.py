"""
Adaptador para la Extracción de Vacantes de LinkedIn y Texto Libre
"""
import re
import json
import logging
from typing import Optional
import httpx
from bs4 import BeautifulSoup
from core.models.vacancy import JobPosting
from adapters.llm.gemini_adapter import GeminiAdapter

logger = logging.getLogger(__name__)


class LinkedInScraperAdapter:
    """Extrae datos de ofertas laborales en LinkedIn o texto libre."""

    def __init__(self, llm_adapter: Optional[GeminiAdapter] = None):
        self.llm = llm_adapter or GeminiAdapter()
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }

    async def extract_from_url(self, url: str) -> JobPosting:
        """
        Intenta extraer la vacante desde la URL pública de LinkedIn.
        Si LinkedIn activa authwall/bloqueo, lanza una excepción informativa para el fallback.
        """
        logger.info(f"Obteniendo información de la vacante: {url}")

        try:
            async with httpx.AsyncClient(headers=self.headers, follow_redirects=True, timeout=15.0) as client:
                response = await client.get(url)

            if response.status_code != 200:
                raise ValueError(f"LinkedIn devolvió código HTTP {response.status_code}")

            html = response.text
            soup = BeautifulSoup(html, "html.parser")

            # 1. Intentar extraer mediante microdatos JSON-LD (formato estándar de vacantes en LinkedIn)
            json_ld_scripts = soup.find_all("script", type="application/ld+json")
            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and data.get("@type") == "JobPosting":
                        logger.info("Vacante extraída con éxito mediante JSON-LD estructurado.")
                        raw_description = BeautifulSoup(data.get("description", ""), "html.parser").get_text("\n")
                        extracted_text = (
                            f"Título: {data.get('title')}\n"
                            f"Empresa: {data.get('hiringOrganization', {}).get('name')}\n"
                            f"Ubicación: {data.get('jobLocation', {}).get('address', {}).get('addressLocality', '')}\n"
                            f"Descripción:\n{raw_description}"
                        )
                        return await self.llm.parse_vacancy_text(extracted_text, source_url=url)
                except Exception as ex:
                    logger.debug(f"Error parseando script JSON-LD: {ex}")

            # 2. Intentar extraer mediante meta tags OpenGraph
            og_title = soup.find("meta", property="og:title")
            og_desc = soup.find("meta", property="og:description")

            # Buscar selector común de descripción de empleo en LinkedIn
            job_desc_elem = (
                soup.find("div", class_=re.compile(r"description__text|show-more-less-html__markup"))
                or soup.find("section", class_=re.compile(r"description"))
            )
            job_desc_text = job_desc_elem.get_text("\n") if job_desc_elem else (og_desc["content"] if og_desc else "")

            combined_text = f"URL: {url}\n"
            if og_title:
                combined_text += f"Meta Título: {og_title.get('content', '')}\n"
            if job_desc_text:
                combined_text += f"Descripción del puesto:\n{job_desc_text}\n"

            # Si el texto obtenido es muy corto, probablemente LinkedIn activó la pantalla de inicio de sesión
            if len(combined_text.strip()) < 150:
                raise ValueError(
                    "LinkedIn requiere inicio de sesión para ver esta publicación pública. "
                    "Por favor, copia el texto de la vacante y pégalo directamente en el chat."
                )

            return await self.llm.parse_vacancy_text(combined_text, source_url=url)

        except Exception as e:
            logger.warning(f"No se pudo extraer directamente por HTTP: {e}")
            raise

    async def extract_from_raw_text(self, text: str, source_url: Optional[str] = None) -> JobPosting:
        """Procesa directamente el texto copiado de una vacante de empleo."""
        logger.info("Analizando texto manual de la vacante con Gemini")
        return await self.llm.parse_vacancy_text(text, source_url=source_url)
