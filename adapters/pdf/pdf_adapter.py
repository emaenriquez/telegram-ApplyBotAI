"""
Adaptador de Generación de PDFs para CVs
Renderiza plantillas HTML + CSS semánticas a documentos PDF vectoriales y compatibles con ATS.
"""
import os
import logging
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from config.settings import settings
from core.models.tailored_cv import TailoredCV

logger = logging.getLogger(__name__)


class PDFAdapter:
    """Implementación de generación de PDF usando Jinja2 y Playwright (o Weasyprint)."""

    def __init__(self):
        settings.ensure_directories()
        self.templates_base = Path(settings.PDF_TEMPLATES_DIR)
        self.output_dir = Path(settings.GENERATED_CVS_DIR)

    async def render_cv_to_pdf(
        self,
        cv: TailoredCV,
        output_filename: str,
        template_name: str = "modern_ats"
    ) -> str:
        """
        Renderiza la plantilla HTML/CSS con los datos del CV adaptado y compila a PDF.
        Retorna la ruta absoluta del archivo PDF generado.
        """
        template_dir = self.templates_base / template_name
        if not template_dir.exists():
            raise FileNotFoundError(f"No se encontró el directorio de plantilla: {template_dir}")

        # Configurar Jinja2
        env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=True
        )
        template = env.get_template("template.html")

        # Renderizar HTML
        rendered_html = template.render(cv=cv)

        # Guardar HTML temporal en la carpeta de salida
        if not output_filename.endswith(".pdf"):
            output_filename += ".pdf"

        html_temp_path = self.output_dir / output_filename.replace(".pdf", ".html")
        pdf_output_path = self.output_dir / output_filename

        with open(html_temp_path, "w", encoding="utf-8") as f:
            f.write(rendered_html)

        # Copiar o referenciar estilos CSS
        css_file = template_dir / "style.css"
        css_content = ""
        if css_file.exists():
            with open(css_file, "r", encoding="utf-8") as f:
                css_content = f.read()

        # Compilar a PDF usando Playwright (Headless Chromium)
        logger.info(f"Compilando PDF: {pdf_output_path}")
        await self._compile_with_playwright(html_temp_path, pdf_output_path, css_content)

        # Eliminar archivo HTML temporal
        try:
            if html_temp_path.exists():
                os.remove(html_temp_path)
        except Exception:
            pass

        return str(pdf_output_path.resolve())

    async def _compile_with_playwright(self, html_path: Path, pdf_path: Path, inline_css: str):
        """Genera el PDF mediante Chromium headless a través de Playwright."""
        try:
            from playwright.async_api import async_playwright

            # ponytail: Playwright crea dir temporal en Temp del sistema; falla con EPERM
            # bajo sandbox/antivirus. Redirigir a carpeta local ya escribible.
            local_tmp = self.output_dir / ".tmp"
            local_tmp.mkdir(parents=True, exist_ok=True)
            os.environ["TEMP"] = str(local_tmp)
            os.environ["TMP"] = str(local_tmp)
            os.environ["TMPDIR"] = str(local_tmp)

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                file_url = html_path.resolve().as_uri()
                await page.goto(file_url, wait_until="networkidle")

                if inline_css:
                    await page.add_style_tag(content=inline_css)

                # Generar PDF estándar A4
                await page.pdf(
                    path=str(pdf_path),
                    format="A4",
                    print_background=True,
                    margin={"top": "15mm", "bottom": "15mm", "left": "15mm", "right": "15mm"}
                )
                await browser.close()

        except ImportError:
            # Si playwright no está instalado, intentar con weasyprint
            try:
                from weasyprint import HTML, CSS
                HTML(filename=str(html_path)).write_pdf(
                    target=str(pdf_path),
                    stylesheets=[CSS(string=inline_css)] if inline_css else []
                )
            except ImportError:
                raise RuntimeError(
                    "Se requiere 'playwright' o 'weasyprint' para generar PDFs. "
                    "Ejecuta: pip install playwright && playwright install chromium"
                )
