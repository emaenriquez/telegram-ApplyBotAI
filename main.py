"""
Punto de Entrada Principal - AI Job Application Assistant
Inicializa los directorios, base de datos y arranca el bot de Telegram.
"""
import sys
import logging

# Configurar encoding UTF-8 en consolas Windows para evitar errores con emojis
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from config.settings import settings

# Configurar formato de logs
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("main")


def check_dependencies():
    """Verifica si las librerías críticas están instaladas."""
    missing = []
    packages = {
        "telegram": "python-telegram-bot",
        "pydantic": "pydantic",
        "aiosqlite": "aiosqlite",
        "jinja2": "jinja2",
        "httpx": "httpx",
        "bs4": "beautifulsoup4"
    }
    for mod_name, pkg_name in packages.items():
        try:
            __import__(mod_name)
        except ImportError:
            missing.append(pkg_name)
    return missing


def main():
    """Función de arranque."""
    print("=" * 65)
    print("      🚀 AI JOB APPLICATION ASSISTANT - INICIANDO SISTEMA")
    print("=" * 65)

    # 1. Comprobar dependencias de Python
    missing = check_dependencies()
    if missing:
        print("\n📦 AVISO DE DEPENDENCIAS:")
        print(f"Faltan paquetes por instalar: {', '.join(missing)}")
        print("Para instalarlos, ejecuta en tu terminal:")
        print("   pip install -r requirements.txt\n")

    # 2. Comprobar variables de entorno esenciales
    if not settings.TELEGRAM_BOT_TOKEN:
        print("⚠️ AVISO DE CONFIGURACIÓN:")
        print("El archivo '.env' fue creado pero 'TELEGRAM_BOT_TOKEN' está vacío.")
        print("Para arrancar el bot de Telegram:")
        print("  1. Abre el archivo '.env' en la raíz del proyecto.")
        print("  2. Coloca tu token de Telegram (obtenido de @BotFather).")
        print("  3. Coloca tu 'GEMINI_API_KEY' (obtenida de Google AI Studio).")
        print("  4. Vuelve a ejecutar: python main.py\n")
        print("Toda la lógica del sistema, base de datos, plantillas y adaptadores están listos.")
        print("=" * 65)
        sys.exit(0)

    # Si hay paquetes faltantes, no continuar hacia el bot
    if missing:
        print("⛔ Por favor instala las dependencias antes de iniciar el bot.")
        sys.exit(1)

    # 3. Crear directorios necesarios (síncrono, no necesita event loop)
    logger.info("Inicializando directorios de trabajo...")
    settings.ensure_directories()

    # 4. Arrancar bot de Telegram con reintentos ante timeout de red
    from adapters.bot.telegram_bot import TelegramAssistantBot

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            bot_adapter = TelegramAssistantBot()
            telegram_app = bot_adapter.build_application()

            print("\n✅ Bot iniciado exitosamente.")
            print("Esperando mensajes y enlaces de LinkedIn en Telegram...\n")
            telegram_app.run_polling()
            break  # Si run_polling termina limpiamente, salir

        except Exception as e:
            error_str = str(e).lower()
            if ("timed out" in error_str or "connect" in error_str) and attempt < max_retries:
                import time
                wait = attempt * 10
                print(f"\n⚠️ Timeout al conectar con Telegram (intento {attempt}/{max_retries}).")
                print(f"   Reintentando en {wait} segundos...\n")
                time.sleep(wait)
            else:
                print(f"\n❌ Error al iniciar el bot: {e}")
                if "timed out" in error_str or "connect" in error_str:
                    print("\n💡 Sugerencias:")
                    print("   • Verifica tu conexión a internet.")
                    print("   • Comprueba que puedas acceder a https://api.telegram.org")
                    print("   • Si usas VPN o proxy, asegúrate de que no bloquee Telegram.")
                raise


if __name__ == "__main__":
    main()
