import os
import json
from groq import Groq
from src.utils import logger, retry_on_failure

class QuestionGenerator:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            # Fallback for old env var name just in case, or raise error
            raise ValueError("GROQ_API_KEY not found")
        
        self.client = Groq(api_key=self.api_key)
        # Using Llama 3.3 70b (Current supported model as of 2025/2026)
        self.model = "llama-3.3-70b-versatile"

    def generate_questions(self, topic_title, content_text, enriched_context=None, 
                          personalized_instructions="", related_topics_context=""):
        """
        Generates 9 questions based on the content using Groq, con personalización inteligente.
        
        Args:
            topic_title: Título del tema
            content_text: Contenido base (de Notion)
            enriched_context: Contexto enriquecido con información de internet (opcional)
            personalized_instructions: Instrucciones personalizadas basadas en historial
            related_topics_context: Contexto de temas relacionados
        """
        # Usar contexto enriquecido si está disponible, sino usar solo el contenido base
        final_context = enriched_context if enriched_context else content_text
        
        # Detectar si hay información de internet en el contexto
        has_web_info = "=== Información complementaria de internet ===" in final_context
        
        web_instruction = ""
        if has_web_info:
            web_instruction = """
        
        IMPORTANTE: El contexto incluye información complementaria de internet (marcada con "===").
        Usa esta información para:
        - Enriquecer las preguntas con ejemplos reales y casos prácticos actuales
        - Incluir detalles técnicos actualizados que puedan no estar en el contenido base
        - Crear casos de estudio más realistas basados en situaciones del mundo real
        - Priorizar información del contenido base, pero complementar con datos de internet cuando sea relevante
        """
        
        # Instrucciones personalizadas del coach
        coach_instruction = ""
        if personalized_instructions:
            coach_instruction = f"""
        
        === INSTRUCCIONES PERSONALIZADAS DEL COACH ===
        {personalized_instructions}
        === FIN INSTRUCCIONES PERSONALIZADAS ===
        """
        
        # Contexto de temas relacionados
        related_instruction = ""
        if related_topics_context:
            related_instruction = f"""
        
        {related_topics_context}
        Considera estos temas relacionados al generar preguntas que conecten conceptos.
        """
        
        prompt = f"""
        Actúa como un **EXAMINADOR TÉCNICO SENIOR** (Nivel Experto).
        
        Objetivo: Generar un examen PROFUNDO y PRÁCTICO basado en el siguiente texto ("{topic_title}").
        
        {coach_instruction}
        {related_instruction}
        {web_instruction}
        
        === ESTRATEGIA DE PREGUNTAS (EXTRACCIÓN Y ATAQUE) ===
        1.  **Analiza Técnicamente:** Busca en el texto datos duros: payloads exactos, comandos de terminal, dosis, configuraciones, flags, errores específicos, o líneas de código.
        2.  **Genera Escenarios:**
            *   NO preguntes "¿Qué es X?".
            *   SÍ pregunta: "Estás en la situación Y, tienes el error Z. Escribe el comando exacto para solucionarlo basado en el texto."
            *   SÍ pregunta: "Calcula la dosis para un paciente de 20kg usando la fórmula del texto."
            *   SÍ pregunta: "Completa el payload de inyección faltante para bypasser el filtro X."

        === FORMATO REQUERIDO (JSON) ===
        Debes devolver un JSON válido con estas 3 categorías:

        1.  "easy" (Básicas pero precisas): Definiciones técnicas, flags de comandos, puertos por defecto, sintaxis básica.
        2.  "development" (Análisis): Explicar POR QUÉ funciona un payload, comparar dos métodos del texto, analizar un snippet de código.
        3.  "case_study" (Aplicación Real - LA MÁS IMPORTANTE):
            *   Plantea un escenario realista (un servidor caído, un paciente enfermo, una auditoría).
            *   El usuario debe "resolverlo" aplicando un dato específico del texto.
            *   La respuesta debe ser la solución técnica exacta.

        === REGLAS CRÍTICAS ===
        *   **Prohibido** preguntas genéricas como "¿Qué nos dice el texto?".
        *   Usa vocabulario técnico avanzado.
        *   Si el texto tiene código, OBLIGA al usuario a interpretar o completar código.
        *   Idioma: Español (pero mantén términos técnicos en inglés si aplica, ej: "payload", "buffer overflow").

        Estructura JSON exacta:
        {{
            "easy": [
                {{ "question": "...", "answer": "..." }},
                {{ "question": "...", "answer": "..." }}
            ],
            "development": [
                {{ "question": "...", "answer": "..." }},
                {{ "question": "...", "answer": "..." }}
            ],
            "case_study": [
                {{ "question": "...", "answer": "..." }},
                {{ "question": "...", "answer": "..." }}
            ]
        }}

        Texto base (Contexto Técnico):
        {final_context[:7000]} 
        """
        # Reducido a 7000 para dejar espacio a instrucciones personalizadas

        try:
            return self._generate_with_retry(prompt)
        except Exception as e:
            logger.error(f"Error generating AI content with Groq: {e}")
            return None
    
    @retry_on_failure(max_attempts=3, delay=2.0)
    def _generate_with_retry(self, prompt: str) -> dict:
        """Genera preguntas con retry logic."""
        chat_completion = self.client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "Eres un asistente útil que genera preguntas de examen en formato JSON puro."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model=self.model,
            temperature=0.5,
            stop=None,
            stream=False,
            response_format={"type": "json_object"}
        )

        response_text = chat_completion.choices[0].message.content
        
        # Clean up potential markdown code blocks if the model adds them
        if "```json" in response_text:
            response_text = response_text.replace("```json", "").replace("```", "")
        
        return json.loads(response_text)
