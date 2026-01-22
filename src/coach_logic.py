"""
Lógica de coaching inteligente: selección de temas, spaced repetition, y personalización.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from src.utils import logger
import math


class CoachLogic:
    """Lógica inteligente de coaching que actúa como un tutor que conoce todo el historial."""
    
    def __init__(self, state_manager):
        self.state_manager = state_manager
    
    def calculate_spaced_repetition_score(self, page_id: str, page_state: Dict) -> float:
        """
        Calcula score basado en spaced repetition (curva de olvido de Ebbinghaus).
        Temas más antiguos y con peor rendimiento tienen mayor prioridad.
        
        Returns:
            float: Score entre 0 y 10 (mayor = más urgente repasar)
        """
        if not page_state or "last_reviewed" not in page_state:
            return 10.0  # Nunca revisado = máxima prioridad
        
        last_reviewed_str = page_state.get("last_reviewed")
        if not last_reviewed_str:
            return 10.0
        
        try:
            last_reviewed = datetime.strptime(last_reviewed_str, "%Y-%m-%d")
            days_since = (datetime.now() - last_reviewed).days
        except:
            return 10.0
        
        # Curva de olvido: después de 1 día olvidas ~50%, después de 7 días ~80%
        # Fórmula: score = 10 * (1 - e^(-days/forgetting_constant))
        forgetting_constant = 2.0  # Ajustable: menor = olvidas más rápido
        retention = math.exp(-days_since / forgetting_constant)
        forgetfulness_score = 10 * (1 - retention)
        
        # Ajustar por rendimiento previo
        perf = page_state.get("performance", [])
        if perf:
            recent_perf = perf[-3:]  # Últimas 3 evaluaciones
            avg_performance = sum(
                3 if p.get("level") == "alto" else 
                2 if p.get("level") == "medio" else 1
                for p in recent_perf
            ) / len(recent_perf)
            
            # Si rendimiento bajo, aumentar urgencia
            performance_multiplier = 1.0 + (3 - avg_performance) * 0.3
            forgetfulness_score *= performance_multiplier
        
        # === STARVATION BOOST (Anti-Abandono) ===
        # Si un tema no se revisa en mucho tiempo, sumar puntos extra garantizados.
        # +0.1 puntos por cada día sin revisar. 
        # Ejemplo: 30 días sin ver = +3.0 puntos (suficiente para superar a temas recientes)
        starvation_boost = days_since * 0.1
        final_score = forgetfulness_score + starvation_boost
        
        return min(25.0, final_score) # Subimos el techo máximo para permitir acumulacion por starvation
    
    def get_learning_gaps(self, page_id: str, page_state: Dict) -> List[str]:
        """
        Extrae gaps de conocimiento identificados en evaluaciones previas.
        
        Returns:
            List[str]: Lista de conceptos/conceptos que necesitan repaso
        """
        gaps = []
        perf = page_state.get("performance", [])
        
        for evaluation in perf[-5:]:  # Últimas 5 evaluaciones
            eval_data = evaluation.get("evaluation", {})
            gaps_list = eval_data.get("gaps", [])
            if gaps_list:
                gaps.extend(gaps_list)
        
        # Devolver gaps únicos más frecuentes
        gap_counts = {}
        for gap in gaps:
            gap_counts[gap] = gap_counts.get(gap, 0) + 1
        
        # Ordenar por frecuencia y devolver top 5
        sorted_gaps = sorted(gap_counts.items(), key=lambda x: x[1], reverse=True)
        return [gap for gap, _ in sorted_gaps[:5]]
    
    def get_related_topics_context(self, all_pages: List[Dict], current_page_id: str) -> str:
        """
        Obtiene contexto de temas relacionados basado en historial de aprendizaje.
        Temas que se estudiaron cerca en el tiempo o con rendimiento similar.
        
        Returns:
            str: Contexto de temas relacionados para el prompt
        """
        current_state = self.state_manager.get_page_state(current_page_id) or {}
        current_title = current_state.get("title", "")
        current_mastery = current_state.get("mastery_level", "novice")
        
        related = []
        for page in all_pages:
            page_id = page.get("id")
            if page_id == current_page_id:
                continue
            
            page_state = self.state_manager.get_page_state(page_id)
            if not page_state:
                continue
            
            # Buscar temas con mastery similar o estudiados recientemente
            page_mastery = page_state.get("mastery_level", "novice")
            last_reviewed = page_state.get("last_reviewed")
            
            if page_mastery == current_mastery or (last_reviewed and 
                (datetime.now() - datetime.strptime(last_reviewed, "%Y-%m-%d")).days < 7):
                related.append({
                    "title": page_state.get("title", ""),
                    "mastery": page_mastery,
                    "reviews": page_state.get("reviews", 0)
                })
        
        if not related:
            return ""
        
        # Formatear contexto
        related_str = "\n=== Temas relacionados estudiados recientemente ===\n"
        for r in related[:3]:  # Top 3 relacionados
            related_str += f"- {r['title']} (Nivel: {r['mastery']}, Revisado {r['reviews']} veces)\n"
        related_str += "=== Fin temas relacionados ===\n"
        
        return related_str
    
    def get_personalized_instructions(self, page_id: str, page_state: Dict) -> str:
        """
        Genera instrucciones personalizadas para el generador de preguntas
        basadas en el historial completo del estudiante.
        
        Returns:
            str: Instrucciones personalizadas para el prompt
        """
        instructions = []
        
        # Nivel de dominio
        mastery = page_state.get("mastery_level", "novice")
        perf = page_state.get("performance", [])
        reviews = page_state.get("reviews", 0)
        
        if mastery == "novice" or reviews == 0:
            instructions.append(
                "Este es un tema NUEVO o con dominio BAJO. "
                "Genera preguntas FUNDAMENTALES que cubran los conceptos básicos. "
                "Enfócate en definiciones, conceptos clave y aplicaciones básicas."
            )
        elif mastery == "intermediate":
            instructions.append(
                "El estudiante tiene conocimiento INTERMEDIO de este tema. "
                "Genera preguntas que profundicen en detalles técnicos y casos de uso prácticos. "
                "Incluye preguntas que conecten conceptos y requieran análisis."
            )
        else:  # advanced
            instructions.append(
                "El estudiante tiene dominio AVANZADO. "
                "Genera preguntas DESAFIANTES que requieran síntesis, evaluación crítica y casos complejos. "
                "Evita preguntas demasiado básicas - busca profundizar y conectar con otros temas."
            )
        
        # Gaps de conocimiento
        gaps = self.get_learning_gaps(page_id, page_state)
        if gaps:
            gaps_str = ", ".join(gaps[:3])  # Top 3 gaps
            instructions.append(
                f"ATENCIÓN: El estudiante ha tenido dificultades con estos conceptos: {gaps_str}. "
                f"Incluye al menos 2-3 preguntas que refuercen específicamente estos conceptos."
            )
        
        # Tendencia de rendimiento
        if len(perf) >= 3:
            recent = [p.get("level") for p in perf[-3:]]
            if all(l == "alto" for l in recent):
                instructions.append(
                    "El estudiante ha tenido excelente rendimiento reciente. "
                    "Puedes aumentar ligeramente la dificultad para mantener el desafío."
                )
            elif all(l == "bajo" for l in recent):
                instructions.append(
                    "El estudiante ha tenido dificultades recientes. "
                    "Genera preguntas más accesibles y con explicaciones más detalladas en las respuestas."
                )
        
        # Frecuencia de revisión
        if reviews > 5:
            instructions.append(
                f"Este tema ha sido revisado {reviews} veces. "
                "Varía el enfoque de las preguntas para evitar repetición - busca nuevos ángulos y aplicaciones."
            )
        
        return "\n".join(instructions)
    
    def select_best_topic(self, all_pages: List[Dict]) -> Optional[Dict]:
        """
        Selecciona el mejor tema para estudiar usando lógica de coaching inteligente.
        Combina spaced repetition, rendimiento previo, y urgencia.
        
        Returns:
            Dict con 'id', 'title', 'score' del tema seleccionado
        """
        candidates = []
        
        for page in all_pages:
            page_id = page["id"]
            page_state = self.state_manager.get_page_state(page_id) or {}
            
            # Skip si fue revisado hoy (a menos que no haya otros candidatos)
            if self.state_manager.is_reviewed_recently(page_id, days_cooldown=0):
                continue
            
            title = page_state.get("title") or "Untitled"
            
            # Calcular score combinado
            spaced_score = self.calculate_spaced_repetition_score(page_id, page_state)
            
            # Score por rendimiento (bajo rendimiento = mayor prioridad)
            perf = page_state.get("performance", [])
            if perf:
                last_level = perf[-1].get("level", "medio")
                if last_level == "bajo":
                    perf_score = 8.0
                elif last_level == "medio":
                    perf_score = 5.0
                else:
                    perf_score = 2.0
            else:
                perf_score = 10.0  # Nunca evaluado = máxima prioridad
            
            # Score por número de revisiones (menos revisado = más prioridad)
            reviews = page_state.get("reviews", 0)
            review_score = 10.0 / (reviews + 1)
            
            # Score combinado (ponderado)
            total_score = (
                spaced_score * 0.4 +      # 40% spaced repetition
                perf_score * 0.4 +        # 40% rendimiento previo
                review_score * 0.2        # 20% frecuencia de revisión
            )
            
            candidates.append({
                "id": page_id,
                "title": title,
                "score": total_score,
                "page": page
            })
        
        if not candidates:
            # Si no hay candidatos, elegir uno al azar de los revisados hoy
            logger.info("No hay candidatos nuevos. Seleccionando uno para práctica adicional.")
            if all_pages:
                page = all_pages[0]
                page_id = page["id"]
                page_state = self.state_manager.get_page_state(page_id) or {}
                return {
                    "id": page_id,
                    "title": page_state.get("title", "Untitled"),
                    "score": 1.0,
                    "page": page
                }
            return None
        
        # Ordenar por score y seleccionar el mejor
        candidates.sort(key=lambda x: x["score"], reverse=True)
        selected = candidates[0]
        
        logger.info(f"Tema seleccionado: {selected['title']} (score: {selected['score']:.2f})")
        return selected
