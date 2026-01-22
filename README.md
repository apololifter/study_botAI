# 🤖 StudyBot: Tu Coach de Aprendizaje Inteligente

![Python](https://img.shields.io/badge/Python-3.14-blue)
![Groq](https://img.shields.io/badge/AI-Groq%20Llama%203-orange)
![Notion](https://img.shields.io/badge/Integration-Notion-black)
![Telegram](https://img.shields.io/badge/Bot-Telegram-blue)

**StudyBot** es más que un simple bot preguntón; es un **Sistema de Aprendizaje Activo y Autónomo** diseñado para transformar tus notas estáticas de Notion en sesiones de entrenamiento dinámicas de alto impacto.

Usa **Inteligencia Artificial Avanzada (Llama 3.3 vía Groq)** para leer tus apuntes, entender tu contexto, y desafiarte con preguntas que evalúan tu razonamiento, no tu memoria.

![Demo del Bot Funcionando](./docs/screenshots/demo.gif)
*(Placeholder: Aquí iría un GIF del bot enviando preguntas y el usuario respondiendo)*

---

## 🚀 ¿Por qué este proyecto?

La mayoría de los estudiantes toman notas y nunca las vuelven a leer. **StudyBot soluciona la "Curva del Olvido"**:
1.  **Priorización Inteligente:** Elige qué estudiar hoy basándose en qué temas has olvidado más (Spaced Repetition) y en cuáles fallaste recientemente.
2.  **Generación Contextual:** No hace preguntas genéricas. Lee tus notas + Busca en Internet (DuckDuckGo) para crear escenarios reales.
3.  **Evaluación Automática:** Tú respondes en lenguaje natural y la IA te califica (Bajo/Medio/Alto) y te da feedback inmediato.

---

## 🛠️ Arquitectura Técnica

El sistema sigue un flujo ETL (Extract, Transform, Load) potenciado con IA:

![Diagrama de Arquitectura](./docs/screenshots/diagrama_flujo.png)
*(Placeholder: Diagrama mostrando Notion -> Python Script -> AI -> Telegram)*

1.  **Notion Adapter (Recursive):** Extrae contenido de tu "Cerebro Digital" (hasta 5 niveles de profundidad).
2.  **Coach Logic:** Algoritmo que puntúa cada tema según Urgencia = `(Olvido * Rendimiento) + Inanición`.
3.  **AI Generator (RAG):** Genera 6 preguntas técnicas usando "Extraction & Attack Strategy".
4.  **Telegram Interface:** Envía el quiz y escucha tus respuestas en tiempo real.
5.  **AI Evaluator:** Analiza tu respuesta y actualiza la base de datos de progreso.

---

## � Guía de Implementación Paso a Paso

Sigue estos pasos para desplegar tu propio Coach Personal en menos de 15 minutos.

### 1. Preparación de Notion

1.  Ve a [Notion Developers](https://www.notion.so/my-integrations) y crea una **“Internal Integration”**.
    ![Crear Integración Notion](./docs/screenshots/notion_1_integration.png)
2.  Obtén el `Internal Integration Token`.
3.  Ve a tu página principal de notas en Notion.
4.  Dale a los 3 puntos `...` > `Connections` > `Connect to` > Elige tu integración.
    ![Conectar Página](./docs/screenshots/notion_2_connect.png)
5.  Copia el ID de la base de datos (o Page ID) de la URL.

### 2. Creación del Bot de Telegram

1.  Habla con [@BotFather](https://t.me/botfather) en Telegram.
2.  Envía `/newbot` y sigue las instrucciones.
3.  Obtén el `HTTP API TOKEN`.
    ![BotFather Token](./docs/screenshots/telegram_1_token.png)
4.  Obtén tu `Chat ID` personal hablando con [@userinfobot](https://t.me/userinfobot).

### 3. Configuración de IA (Groq)

1.  Registrate gratis en [Groq Console](https://console.groq.com/).
2.  Crea una API Key. (Usamos Groq por su velocidad infernal y capa gratuita generosa).

### 4. Despliegue en GitHub (Ciclo Automático)

Este proyecto está diseñado para correr gratis en **GitHub Actions**.

1.  **Fork/Clone** este repositorio.
2.  Ve a la pestaña **Settings** > **Secrets and variables** > **Actions** en tu repositorio de GitHub.
3.  Crea los siguientes `Repository secrets`:

    | Nombre Secreto | Valor |
    | :--- | :--- |
    | `NOTION_TOKEN` | Tu token "ntn_..." |
    | `NOTION_DATABASE_ID` | El ID de tu página |
    | `TELEGRAM_TOKEN` | Tu token del BotFather |
    | `TELEGRAM_CHAT_ID` | Tu ID numérico |
    | `GROQ_API_KEY` | Tu key "gsk_..." |

    ![GitHub Secrets](./docs/screenshots/github_1_secrets.png)

4.  ¡Listo! El workflow en `.github/workflows/study_schedule.yml` está configurado para ejecutarse **automáticamente cada día** (puedes editar el cron si quieres).

---

## 💻 Ejecución Local (Para Desarrollo)

Si quieres probarlo en tu PC antes de subirlo:

1.  **Clonar:**
    ```bash
    git clone https://github.com/tu-usuario/study-bot.git
    cd study-bot
    ```

2.  **Entorno Virtual:**
    ```bash
    python -m venv venv
    .\venv\Scripts\activate  # Windows
    ```

3.  **Dependencias:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configuración:**
    *   Copia `.env.example` a `.env`.
    *   Pega tus credenciales.

5.  **Correr:**
    ```bash
    python main.py
    ```

---

## � Contribución

¡Las PR son bienvenidas! Si tienes ideas para mejorar la lógica del Coach o añadir más integraciones (Discord, Slack, Obsidian), siéntete libre de abrir un issue.

---

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Úsalo, estúdialo y mejora tu aprendizaje.
