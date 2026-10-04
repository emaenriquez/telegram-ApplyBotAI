"""
Adaptador de Correo Electrónico para Gmail API
Crea borradores en la bandeja de Borradores con el CV adjunto sin enviar el mensaje.
"""
import os
import base64
import logging
from pathlib import Path
from typing import Optional
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from config.settings import settings

logger = logging.getLogger(__name__)

# Permisos mínimos requeridos: componer borradores
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]


class GmailAdapter:
    """Implementación de EmailPort para crear borradores en Gmail."""

    def __init__(self):
        self.credentials_file = settings.GMAIL_CREDENTIALS_FILE
        self.token_file = settings.GMAIL_TOKEN_FILE
        self._service = None

    def _get_service(self):
        """Obtiene o inicializa el cliente autenticado de Gmail API."""
        if self._service:
            return self._service

        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build

            creds = None
            if os.path.exists(self.token_file):
                creds = Credentials.from_authorized_user_file(self.token_file, GMAIL_SCOPES)

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not os.path.exists(self.credentials_file):
                        logger.warning(
                            f"Archivo de credenciales '{self.credentials_file}' no encontrado. "
                            "Para activar la creación de borradores reales en Gmail, descarga las credenciales OAuth 2.0."
                        )
                        return None
                    flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file, GMAIL_SCOPES)
                    creds = flow.run_local_server(port=0)

                with open(self.token_file, "w", encoding="utf-8") as token:
                    token.write(creds.to_json())

            self._service = build("gmail", "v1", credentials=creds)
            return self._service

        except Exception as e:
            logger.error(f"Error autenticando con Gmail API: {e}")
            return None

    async def create_draft(
        self,
        recipient: Optional[str],
        subject: str,
        body: str,
        attachment_path: Optional[str] = None
    ) -> str:
        """
        Crea un borrador en Gmail con el asunto, cuerpo y archivo adjunto.
        Retorna el ID del borrador creado o una simulación si las credenciales aún no se cargaron.
        """
        service = self._get_service()

        message = MIMEMultipart()
        # Gmail rechaza "To" inválido (placeholder o nombre sin email). Sin destinatario válido, omitir To.
        recipient = (recipient or "").strip()
        if recipient and "@" in recipient and " " not in recipient:
            message["to"] = recipient
        else:
            logger.warning(f"Destinatario inválido o ausente ({recipient!r}); borrador sin campo 'To'.")
        message["subject"] = subject

        # Agregar cuerpo
        message.attach(MIMEText(body, "plain", "utf-8"))

        # Adjuntar PDF si existe
        if attachment_path:
            attachment_path = str(attachment_path)
            if os.path.exists(attachment_path):
                filename = Path(attachment_path).name
                # Asegurar que el nombre de archivo tenga extensión .pdf
                if not filename.lower().endswith(".pdf"):
                    filename = filename + ".pdf"

                file_size = os.path.getsize(attachment_path)
                logger.info(f"Adjuntando PDF al borrador: '{filename}' ({file_size} bytes)")

                with open(attachment_path, "rb") as f:
                    pdf_data = f.read()

                part = MIMEBase("application", "pdf", name=filename)
                part.set_payload(pdf_data)
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=filename
                )
                message.attach(part)
                logger.info(f"PDF adjuntado exitosamente: {filename}")
            else:
                logger.warning(f"Archivo PDF no encontrado en la ruta: {attachment_path}")
        else:
            logger.warning("No se proporcionó ruta de PDF para adjuntar al borrador.")

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

        if not service:
            raise RuntimeError(
                "Gmail API no configurado. Falta 'credentials.json' o el token.json no es válido."
            )

        draft_body = {"message": {"raw": raw_message}}
        created_draft = service.users().drafts().create(userId="me", body=draft_body).execute()
        draft_id = created_draft.get("id", "")
        logger.info(f"Borrador creado exitosamente en Gmail con ID: {draft_id}")
        return draft_id
