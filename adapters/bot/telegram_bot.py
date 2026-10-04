"""
Bot de Telegram para AI Job Application Assistant
Gestiona la interacción conversacional, revisión humana y flujos de aprobación.
"""
import os
import logging
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

from config.settings import settings
from services.application_service import ApplicationCoordinatorService
from core.models.application import ApplicationStatus

logger = logging.getLogger(__name__)

# Estados del flujo conversacional (FSM)
WAITING_JOB_INPUT, REVIEWING_PROPOSAL, WAITING_USER_FEEDBACK = range(3)


class TelegramAssistantBot:
    """Implementación del bot conversacional de Telegram con control Human-in-the-loop."""

    def __init__(self, service: Optional[ApplicationCoordinatorService] = None):
        self.service = service or ApplicationCoordinatorService()
        self.allowed_user_id = settings.TELEGRAM_ALLOWED_USER_ID

    def _is_authorized(self, update: Update) -> bool:
        """Verifica si el usuario de Telegram está autorizado."""
        if not self.allowed_user_id:
            return True
        user = update.effective_user
        return bool(user and user.id == self.allowed_user_id)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Manejador del comando /start."""
        if not self._is_authorized(update):
            await update.message.reply_text("Lo siento, este bot es privado y no estás autorizado.")
            return ConversationHandler.END

        profiles = self.service.load_base_profiles()
        profiles_list = "\n".join([f"• `{p.id}`: {p.headline}" for p in profiles]) if profiles else "⚠️ Ninguno cargado aún."

        welcome_text = (
            "**¡Hola! Soy tu AI Job Application Assistant.**\n\n"
            "Te ayudo a analizar vacantes de LinkedIn, adaptar tu CV al puesto, "
            "generar un PDF profesional y crear un borrador de correo listo para enviar.\n\n"
            "**Perfiles base disponibles:**\n"
            f"{profiles_list}\n\n"
            "**Para comenzar:**\n"
            "Envíame el **enlace de una vacante de LinkedIn** o pega directamente la descripción del empleo."
        )
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)
        return WAITING_JOB_INPUT

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja el comando /status para chequear la configuración."""
        if not self._is_authorized(update):
            return

        gemini_ok = "Configurada" if settings.GEMINI_API_KEY else "Pendiente en .env"
        bot_ok = "Activo" if settings.TELEGRAM_BOT_TOKEN else "Pendiente en .v"
        gmail_ok = "Listo" if os.path.exists(settings.GMAIL_CREDENTIALS_FILE) else "Falta credentials.json"

        profiles = self.service.load_base_profiles()

        status_msg = (
            "**Estado del Sistema:**\n\n"
            f"• **Telegram Bot:** {bot_ok}\n"
            f"• **Google Gemini ({settings.GEMINI_MODEL}):** {gemini_ok}\n"
            f"• **Gmail API:** {gmail_ok}\n"
            f"• **Perfiles base cargados:** {len(profiles)}\n"
            f"• **Base de datos:** `{settings.DATABASE_PATH}`\n"
        )
        await update.message.reply_text(status_msg, parse_mode=ParseMode.MARKDOWN)

    async def history_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja el comando /history mostrando las últimas postulaciones."""
        if not self._is_authorized(update):
            return

        recent = await self.service.storage.get_recent_applications(limit=5)
        if not recent:
            await update.message.reply_text("📂 No hay postulaciones registradas en el historial.")
            return

        lines = ["📋 **Últimas postulaciones analizadas:**\n"]
        for r in recent:
            date_str = r.created_at.strftime("%d/%m/%Y %H:%M")
            lines.append(
                f"• **{r.company_name}** - {r.vacancy_title}\n"
                f"  Compatibilidad: `{r.match_percentage}%` | Estado: `{r.status}`\n"
                f"  Fecha: {date_str}\n"
            )

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancela la operación actual."""
        context.user_data.clear()
        await update.message.reply_text("Proceso cancelado. Envíame un nuevo enlace cuando quieras.")
        return ConversationHandler.END

    async def handle_job_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Recibe el link de LinkedIn o texto libre y realiza el análisis inicial."""
        if not self._is_authorized(update):
            return ConversationHandler.END

        user_input = update.message.text.strip()
        status_msg = await update.message.reply_text("⏳ Obteniendo información de la vacante y analizando requisitos con Gemini...")

        try:
            # 1. Extraer vacante
            try:
                vacancy = await self.service.process_vacancy_input(user_input)
            except Exception as ex:
                await status_msg.edit_text(
                    f" No pude acceder directamente al enlace ({ex}).\n\n"
                    "Por favor, **copia el texto completo de la vacante de LinkedIn y pégalo aquí** directamente para continuar."
                )
                return WAITING_JOB_INPUT

            # 2. Analizar compatibilidad con perfiles
            await status_msg.edit_text("Evaluando compatibilidad con tus perfiles y seleccionando el CV más adecuado...")
            match_result, selected_profile = await self.service.analyze_vacancy(vacancy)

            # 3. Adaptar el CV a la vacante
            await status_msg.edit_text("Adaptando el perfil y optimizando viñetas para ATS...")
            tailored_cv = await self.service.generate_tailored_cv(vacancy, selected_profile)

            # Guardar en sesión del usuario
            context.user_data["vacancy"] = vacancy
            context.user_data["match_result"] = match_result
            context.user_data["selected_profile"] = selected_profile
            context.user_data["tailored_cv"] = tailored_cv

            # Formatear reporte de revisión para el usuario
            matching_str = ", ".join(match_result.matching_skills[:6]) if match_result.matching_skills else "Detectadas en historial"
            missing_str = ", ".join(match_result.missing_skills[:5]) if match_result.missing_skills else "Ninguna brecha crítica"

            # Información de contacto detectada
            contact_info = ""
            if vacancy.recruiter_email:
                contact_info += f"📧 **Email detectado:** `{vacancy.recruiter_email}`\n"
            if vacancy.required_email_subject:
                contact_info += f"📌 **Asunto obligatorio:** `{vacancy.required_email_subject}`\n"

            response_text = (
                f"**Puesto:** {vacancy.title}\n"
                f"**Empresa:** {vacancy.company}\n"
                f"**Ubicación:** {vacancy.location} ({vacancy.workplace_type})\n\n"
                f"**Compatibilidad ATS:** `{match_result.match_percentage}%`\n"
                f"**CV Base Usado:** `{selected_profile.id}`\n\n"
                f"**Coincidencias clave:** {matching_str}\n"
                f"**Habilidades faltantes/deseables:** {missing_str}\n\n"
                f"{contact_info}"
                f"**Estrategia aplicada:**\n"
                f"{tailored_cv.tailoring_rationale}"
            )

            keyboard = [
                [
                    InlineKeyboardButton("Generar PDF y Borrador", callback_data="approve_all"),
                    InlineKeyboardButton("Solo Generar PDF", callback_data="only_pdf")
                ],
                [
                    InlineKeyboardButton("Solicitar Ajustes", callback_data="request_changes"),
                    InlineKeyboardButton("Descartar", callback_data="discard")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await status_msg.delete()
            await update.message.reply_text(response_text, parse_mode=ParseMode.MARKDOWN)
            await update.message.reply_text(self._format_cv_preview(tailored_cv), parse_mode=ParseMode.MARKDOWN)
            await update.message.reply_text("¿Qué deseas hacer a continuación?", reply_markup=reply_markup)
            return REVIEWING_PROPOSAL

        except Exception as e:
            logger.error(f"Error procesando vacante: {e}", exc_info=True)
            error_str = str(e).lower()
            if any(code in error_str for code in ["503", "429", "unavailable", "high demand", "overloaded"]):
                error_msg = (
                    "**Gemini está temporalmente saturado** (error 503).\n\n"
                    "El sistema ya reintentó automáticamente 3 veces con espera.\n"
                    "Esto suele resolverse en unos minutos. Vuelve a enviar el enlace en un momento."
                )
            else:
                error_msg = f"Ocurrió un error al procesar la vacante:\n`{str(e)}`"
            await status_msg.edit_text(error_msg, parse_mode=ParseMode.MARKDOWN)
            return WAITING_JOB_INPUT

    @staticmethod
    def _options_keyboard() -> InlineKeyboardMarkup:
        """Teclado principal de opciones tras el análisis."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Generar PDF y Borrador", callback_data="approve_all"),
                InlineKeyboardButton("Solo Generar PDF", callback_data="only_pdf")
            ],
            [
                InlineKeyboardButton("Solicitar Ajustes", callback_data="request_changes"),
                InlineKeyboardButton("Descartar", callback_data="discard")
            ]
        ])

    @staticmethod
    def _format_cv_preview(cv) -> str:
        """Formatea el CV adaptado completo como texto para revisión previa."""
        lines = ["📄 **Vista previa del CV adaptado**\n"]
        lines.append(f"**{cv.full_name}** — {cv.headline}\n")

        contact = []
        if cv.email:
            contact.append(f"📧 {cv.email}")
        if cv.phone:
            contact.append(f"📱 {cv.phone}")
        if cv.location:
            contact.append(f"📍 {cv.location}")
        if contact:
            lines.append(" · ".join(contact) + "\n")

        if cv.summary:
            lines.append("**Resumen**\n" + cv.summary + "\n")

        if cv.highlighted_skills:
            lines.append("**Habilidades**\n" + ", ".join(cv.highlighted_skills) + "\n")

        if cv.experience:
            lines.append("**Experiencia Laboral**")
            for exp in cv.experience:
                lines.append(f"\n• *{exp.role}* — {exp.company} ({exp.start_date} – {exp.end_date})")
                for ach in exp.achievements:
                    lines.append(f"    - {ach}")

        if cv.projects:
            lines.append("\n**Proyectos**")
            for proj in cv.projects:
                lines.append(f"\n• *{proj.name}*: {proj.description}")

        if cv.education:
            lines.append("\n**Educación**")
            for edu in cv.education:
                lines.append(f"\n• {edu.degree} — {edu.institution} ({edu.year})")

        if cv.languages:
            lines.append("\n**Idiomas**\n" + ", ".join(cv.languages))

        return "\n".join(lines)

    async def handle_proposal_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Maneja las acciones de los botones interactivos."""
        query = update.callback_query
        await query.answer()

        action = query.data
        vacancy = context.user_data.get("vacancy")
        tailored_cv = context.user_data.get("tailored_cv")
        match_result = context.user_data.get("match_result")
        selected_profile = context.user_data.get("selected_profile")

        if action == "discard":
            await query.edit_message_text("❌ Postulación descartada. Puedes enviar otra vacante cuando gustes.")
            context.user_data.clear()
            return ConversationHandler.END

        if action == "request_changes":
            await query.edit_message_text(
                "**Solicitud de ajustes:**\n\n"
                "Escribe las instrucciones específicas que deseas que la IA aplique al CV.\n"
                "Ejemplo: *'Enfócate más en proyectos de AWS y quita la mención de Django'*"
            )
            return WAITING_USER_FEEDBACK

        if action in ("approve_all", "only_pdf"):
            await query.edit_message_text("⚙️ **Compilando PDF profesional...**")

            try:
                # 1. Compilar PDF
                pdf_path = await self.service.compile_pdf(
                    cv=tailored_cv,
                    company_name=vacancy.company,
                    job_title=vacancy.title
                )

                # 2. Enviar documento PDF por Telegram
                with open(pdf_path, "rb") as pdf_file:
                    await context.bot.send_document(
                        chat_id=query.message.chat_id,
                        document=pdf_file,
                        caption=f"📄 **CV generado:** {vacancy.company} - {vacancy.title}",
                        parse_mode=ParseMode.MARKDOWN
                    )

                draft_id = None
                if action == "approve_all":
                    await query.message.reply_text("✉️ Redactando email y creando borrador en Gmail...")
                    proposal, draft_id = await self.service.prepare_email_draft(
                        vacancy=vacancy,
                        cv=tailored_cv,
                        pdf_path=pdf_path
                    )

                    email_msg = (
                        "📬 **¡Borrador creado en Gmail!**\n\n"
                        f"• **Destinatario:** `{proposal.recipient or 'Pendiente'}`\n"
                        f"• **Asunto:** `{proposal.subject}`\n"
                        f"• **Adjunto:** `{os.path.basename(pdf_path)}`\n\n"
                        "📝 **Cuerpo del correo preparado:**\n"
                        f"```\n{proposal.body}\n```\n\n"
                        "🔒 *El correo quedó guardado en tu carpeta 'Borradores' para que lo revises antes de enviarlo.*"
                    )
                    await query.message.reply_text(email_msg, parse_mode=ParseMode.MARKDOWN)

                # 3. Guardar en base de datos
                app_id = await self.service.record_application(
                    vacancy=vacancy,
                    match_score=match_result.match_percentage,
                    base_cv_id=selected_profile.id,
                    pdf_path=pdf_path,
                    draft_id=draft_id
                )

                if action == "approve_all":
                    await query.message.reply_text(
                        f"✅ **Postulación registrada exitosamente** (ID: `#{app_id}`).\n"
                        "¡Listo para enviar cuando tú decidas! Envía otra vacante para procesar."
                    )
                    context.user_data.clear()
                    return ConversationHandler.END

                # only_pdf: dejar la puerta abierta para crear el email después
                context.user_data["pdf_path"] = pdf_path
                context.user_data["app_id"] = app_id

                await query.edit_message_text("📄 **PDF generado y enviado por Telegram.**")
                follow_up = (
                    f"✅ **Postulación registrada** (ID: `#{app_id}`).\n"
                    "PDF listo. ¿Quieres crear también el borrador de email?"
                )
                follow_keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("✉️ Enviar email", callback_data="send_email_now"),
                    InlineKeyboardButton("✅ Terminar", callback_data="finish")
                ]])
                await query.message.reply_text(follow_up, reply_markup=follow_keyboard, parse_mode=ParseMode.MARKDOWN)
                return REVIEWING_PROPOSAL

            except Exception as e:
                logger.error(f"Error generando PDF o borrador: {e}", exc_info=True)
                await query.message.reply_text(
                    f"❌ Ocurrió un error en la generación:\n`{str(e)}`\n\n"
                    "Puedes reintentarlo o elegir otra opción:",
                    reply_markup=self._options_keyboard(),
                    parse_mode=ParseMode.MARKDOWN
                )
                return REVIEWING_PROPOSAL

        if action == "send_email_now":
            pdf_path = context.user_data.get("pdf_path")
            app_id = context.user_data.get("app_id")
            if not pdf_path or not vacancy or not tailored_cv:
                await query.edit_message_text("❌ No hay datos para generar el email. Envía una nueva vacante.")
                context.user_data.clear()
                return ConversationHandler.END

            await query.edit_message_text("✉️ Redactando email y creando borrador en Gmail...")
            try:
                proposal, draft_id = await self.service.prepare_email_draft(
                    vacancy=vacancy,
                    cv=tailored_cv,
                    pdf_path=pdf_path
                )
                if app_id is not None:
                    await self.service.storage.update_status(
                        app_id, ApplicationStatus.DRAFT_CREATED, draft_id=draft_id
                    )

                email_msg = (
                    "📬 **¡Borrador creado en Gmail!**\n\n"
                    f"• **Destinatario:** `{proposal.recipient or 'Pendiente'}`\n"
                    f"• **Asunto:** `{proposal.subject}`\n"
                    f"• **Adjunto:** `{os.path.basename(pdf_path)}`\n\n"
                    "📝 **Cuerpo del correo preparado:**\n"
                    f"```\n{proposal.body}\n```\n\n"
                    "🔒 *El correo quedó guardado en tu carpeta 'Borradores' para que lo revises antes de enviarlo.*"
                )
                await query.message.reply_text(email_msg, parse_mode=ParseMode.MARKDOWN)
            except Exception as e:
                logger.error(f"Error creando borrador de email: {e}", exc_info=True)
                await query.message.reply_text(
                    f"❌ Ocurrió un error creando el email:\n`{str(e)}`\n\n"
                    "Puedes reintentarlo:",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("✉️ Reintentar email", callback_data="send_email_now"),
                        InlineKeyboardButton("✅ Terminar", callback_data="finish")
                    ]]),
                    parse_mode=ParseMode.MARKDOWN
                )
                return REVIEWING_PROPOSAL
            context.user_data.clear()
            return ConversationHandler.END

        if action == "finish":
            await query.edit_message_text("✅ Proceso finalizado. Envía otra vacante cuando quieras.")
            context.user_data.clear()
            return ConversationHandler.END

        return REVIEWING_PROPOSAL

    async def handle_user_feedback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Recibe el texto de ajuste del usuario y regenera la adaptación del CV."""
        user_feedback = update.message.text.strip()
        status_msg = await update.message.reply_text("🔄 Re-adaptando el CV con tus indicaciones...")

        vacancy = context.user_data.get("vacancy")
        selected_profile = context.user_data.get("selected_profile")
        match_result = context.user_data.get("match_result")

        try:
            # Re-adaptar CV con el nuevo feedback
            updated_cv = await self.service.generate_tailored_cv(
                vacancy=vacancy,
                profile=selected_profile,
                user_feedback=user_feedback
            )
            context.user_data["tailored_cv"] = updated_cv

            response_text = (
                f"✨ **CV Re-adaptado con tus ajustes:**\n\n"
                f"🎯 **Puesto:** {vacancy.title} en {vacancy.company}\n\n"
                f"💡 **Racional actualizado:**\n{updated_cv.tailoring_rationale}"
            )

            keyboard = [
                [
                    InlineKeyboardButton("✅ Generar PDF y Borrador", callback_data="approve_all"),
                    InlineKeyboardButton("📄 Solo Generar PDF", callback_data="only_pdf")
                ],
                [
                    InlineKeyboardButton("✏️ Ajustar Nuevamente", callback_data="request_changes"),
                    InlineKeyboardButton("❌ Descartar", callback_data="discard")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await status_msg.delete()
            await update.message.reply_text(response_text, parse_mode=ParseMode.MARKDOWN)
            await update.message.reply_text(self._format_cv_preview(updated_cv), parse_mode=ParseMode.MARKDOWN)
            await update.message.reply_text("¿Aprobamos esta versión o deseas otro ajuste?", reply_markup=reply_markup)
            return REVIEWING_PROPOSAL

        except Exception as e:
            logger.error(f"Error re-adaptando CV: {e}", exc_info=True)
            await status_msg.edit_text(f"❌ Ocurrió un error:\n`{str(e)}`")
            return REVIEWING_PROPOSAL

    @staticmethod
    async def _post_init(application: Application) -> None:
        """Hook que se ejecuta después de que el bot arranca, dentro de su event loop."""
        from adapters.storage.sqlite_adapter import SQLiteStorageAdapter
        storage = SQLiteStorageAdapter()
        await storage.init_db()

    def build_application(self) -> Application:
        """Construye y configura la instancia de python-telegram-bot."""
        if not settings.TELEGRAM_BOT_TOKEN:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN está vacío en .env. "
                "Configura tu token obtenido de @BotFather."
            )

        from telegram.request import HTTPXRequest

        # Timeouts amplios para conexiones lentas o inestables
        custom_request = HTTPXRequest(
            connect_timeout=30.0,
            read_timeout=30.0,
            write_timeout=30.0,
            pool_timeout=30.0,
            connection_pool_size=8,
        )

        app = (
            Application.builder()
            .token(settings.TELEGRAM_BOT_TOKEN)
            .request(custom_request)
            .post_init(self._post_init)
            .build()
        )

        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("start", self.start_command),
                MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_job_input)
            ],
            states={
                WAITING_JOB_INPUT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_job_input)
                ],
                REVIEWING_PROPOSAL: [
                    CallbackQueryHandler(self.handle_proposal_action)
                ],
                WAITING_USER_FEEDBACK: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_user_feedback)
                ],
            },
            fallbacks=[
                CommandHandler("cancel", self.cancel_command),
                CommandHandler("start", self.start_command)
            ],
            per_message=False
        )

        app.add_handler(CommandHandler("status", self.status_command))
        app.add_handler(CommandHandler("history", self.history_command))
        app.add_handler(conv_handler)

        return app
