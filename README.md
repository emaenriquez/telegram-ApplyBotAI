# AI Job Application Assistant 🚀

Sistema inteligente desarrollado en Python para automatizar el análisis de vacantes de LinkedIn, evaluar compatibilidad (ATS Fit Score), adaptar el currículum vitae más idóneo mediante Google Gemini, compilar un PDF profesional y crear un borrador de correo en Gmail con el CV adjunto listo para revisión humana.

---

## 📋 Arquitectura del Proyecto

```
automatizacion_linkedin_publicaciones/
├── .env                     # Variables de entorno y credenciales (privado)
├── .env.example             # Plantilla de variables de entorno
├── requirements.txt         # Dependencias del proyecto
├── main.py                  # Punto de entrada principal
│
├── config/                  # Configuración centralizada
│   ├── settings.py          # Gestión de variables con Pydantic Settings
│   └── prompts.py           # Prompts del sistema para Gemini (ATS, CV, Email)
│
├── core/                    # Lógica de dominio y entidades
│   ├── models/              # Modelos Pydantic
│   │   ├── vacancy.py       # JobPosting y MatchScoreResult
│   │   ├── profile.py       # UserProfile, Experiencia, Habilidades
│   │   ├── tailored_cv.py   # TailoredCV y EmailDraftProposal
│   │   └── application.py   # ApplicationRecord y ApplicationStatus
│   └── ports/               # Interfaces abstractas (Clean Architecture)
│
├── adapters/                # Implementaciones externas
│   ├── bot/                 # Telegram Bot (FSM, botones de revisión)
│   ├── llm/                 # Adaptador para Google Gemini
│   ├── scrapers/            # Extractor de LinkedIn y texto libre
│   ├── pdf/                 # Generador de PDF con Jinja2 y Playwright
│   ├── email/               # Integración con Gmail API (Borradores)
│   └── storage/             # Base de datos SQLite asíncrona (aiosqlite)
│
├── templates/               # Plantillas y perfiles
│   ├── base_cvs/            # Perfiles base del usuario en JSON
│   │   ├── cv_backend_python.json
│   │   └── cv_fullstack.json
│   └── pdf_styles/          # Plantillas HTML/CSS para generación de PDF
│       └── modern_ats/
│           ├── template.html
│           └── style.css
│
└── data/                    # Almacenamiento local (generado automáticamente)
    ├── applications.db      # Base de datos histórica
    └── generated_cvs/       # PDFs de CVs generados por vacante
```

---

## 🛠️ Guía Rápida de Instalación y Configuración

### 1. Instalar dependencias

Se recomienda utilizar un entorno virtual de Python:

```bash
# Crear entorno virtual
python -m venv venv

# Activar en Windows PowerShell:
.\venv\Scripts\Activate.ps1

# Instalar dependencias
pip install -r requirements.txt

# Instalar los navegadores de Playwright para generación de PDF
playwright install chromium
```

---

### 2. Configurar el archivo `.env`

Abre el archivo `.env` en la raíz y completa los campos:

```ini
# Token del bot obtenido de @BotFather en Telegram
TELEGRAM_BOT_TOKEN=tu_token_aqui

# (Opcional) Tu ID numérico de Telegram para restringir el uso solo a ti
TELEGRAM_ALLOWED_USER_ID=

# Clave de API de Google Gemini (Google AI Studio: https://aistudio.google.com/)
GEMINI_API_KEY=tu_gemini_api_key_aqui
GEMINI_MODEL=gemini-1.5-pro

# Credenciales de Gmail (opcional para creación de borradores reales)
GMAIL_CREDENTIALS_FILE=credentials.json
GMAIL_TOKEN_FILE=token.json
```

---

### 3. Configurar tu CV Base

En la carpeta `templates/base_cvs/`:

- Encontrarás perfiles de ejemplo (`cv_backend_python.json` y `cv_fullstack.json`).
- Puedes editarlos o agregar nuevos archivos `.json` con tus datos verídicos reales.
- El sistema analizará la vacante y seleccionará automáticamente cuál de tus perfiles base es el más compatible.

---

### 4. (Opcional) Activar Borradores Reales de Gmail

Para que el bot cree los borradores directamente en tu bandeja de Gmail:

1. Dirígete a [Google Cloud Console](https://console.cloud.google.com/).
2. Habilita la **Gmail API**.
3. En la sección _Credentials_, crea un **OAuth 2.0 Client ID** (tipo _Desktop App_).
4. Descarga el archivo JSON y guárdalo en la raíz del proyecto como `credentials.json`.
5. La primera vez que el bot genere un borrador, abrirá una ventana de navegador para autorizar el acceso (alcance exclusivo para componer borradores sin leer tu correo personal).

---

## 🚀 Ejecución del Sistema

Una vez configuradas las credenciales en `.env`, inicia el bot:

```bash
python main.py
```

### Comandos disponibles en Telegram:

- `/start`: Inicia la conversación, lista los perfiles base activos y te pide el enlace o descripción.
- `/status`: Verifica el estado de conexión con Telegram, Gemini y Gmail.
- `/history`: Muestra las últimas 5 vacantes analizadas con su porcentaje de compatibilidad.
- `/cancel`: Cancela el análisis o proceso actual.

---

## 🤖 Flujo de Trabajo en Telegram

1. **Envío de la vacante:** Envía un link de LinkedIn (ej: `https://www.linkedin.com/jobs/view/...`) o pega el texto directamente.
2. **Análisis & Match ATS:** La IA calcula la afinidad (0-100%), identifica coincidencias y habilidades faltantes.
3. **Adaptación:** Adapta el resumen profesional y las viñetas del CV sin alucinaciones.
4. **Revisión Humana:** El bot te presenta un menú interactivo:
   - `[✅ Generar PDF y Borrador]`: Compila el PDF, te lo envía a Telegram y crea el borrador en Gmail con el CV adjunto.
   - `[📄 Solo Generar PDF]`: Solo genera el PDF y te lo envía al chat.
   - `[✏️ Solicitar Ajustes]`: Te permite indicarle cambios específicos a la IA (ej: _"Enfócate más en FastAPI"_).
   - `[❌ Descartar]`: Cancela la postulación.
5. **Registro:** Cada postulación queda guardada en la base de datos SQLite para tu seguimiento histórico.
