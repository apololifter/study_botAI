import os
import json
from typing import Any, Dict

from groq import Groq


class AnswerEvaluator:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not found")
        self.client = Groq(api_key=self.api_key)
        self.model = "llama-3.3-70b-versatile"

    def evaluate_freeform(
        self,
        topic_title: str,
        quiz: Dict[str, Any],
        user_answer_text: str,
    ) -> Dict[str, Any]:
        """
        Evaluates a single freeform user answer (e.g., summary/reflection) against the quiz.
        Returns dict with keys: level (bajo|medio|alto), confidence (0-1), rationale, gaps, suggested_review.
        """

        prompt = f"""
Eres un evaluador estricto pero justo.

Tema: "{topic_title}"

Preguntas y respuestas sugeridas (contexto):
{json.dumps(quiz, ensure_ascii=False)}

Respuesta del estudiante (texto libre):
{user_answer_text}

Tarea:
1) Evalúa qué tan bien responde/explica el contenido relevante del tema.
2) Clasifica el rendimiento en UNA de estas categorías exactas: "bajo rendimiento", "medio rendimiento", "alto rendimiento".
3) Devuelve SOLO JSON válido con esta estructura exacta:
{{
  "level": "bajo" | "medio" | "alto",
  "confidence": 0.0,
  "rationale": "2-5 frases",
  "gaps": ["lista corta de conceptos faltantes o errores"],
  "suggested_review": ["3 bullets concretos de qué repasar"]
}}

Reglas:
- No uses markdown. No agregues texto fuera del JSON.
- Mapea: "bajo rendimiento"->"bajo", "medio rendimiento"->"medio", "alto rendimiento"->"alto".
"""

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "Devuelve exclusivamente JSON válido siguiendo el esquema."},
                    {"role": "user", "content": prompt},
                ],
                model=self.model,
                temperature=0.2,
                stream=False,
                response_format={"type": "json_object"},
            )

            response_text = chat_completion.choices[0].message.content
            
            # Clean up potential markdown code blocks if the model adds them
            if "```" in response_text:
                response_text = response_text.replace("```json", "").replace("```", "")
            
            data = json.loads(response_text)

            # Normalize level just in case
            level = str(data.get("level", "")).strip().lower()
            if level not in {"bajo", "medio", "alto"}:
                # fallback mapping from phrase
                if "alto" in level:
                    level = "alto"
                elif "medio" in level:
                    level = "medio"
                else:
                    level = "bajo"
                data["level"] = level

            return data

        except Exception as e:
            print(f"Error generating AI evaluation with Groq: {e}")
            # Fallback structure on error
            return {
                "level": "bajo",
                "confidence": 0.0,
                "rationale": "Error en evaluación automática.",
                "gaps": [],
                "suggested_review": []
            }
