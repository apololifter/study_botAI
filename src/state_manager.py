import json
import os
import shutil
import time
from datetime import datetime
from src.utils import logger

STATE_FILE = "data/state.json"
STATE_BACKUP = "data/state.json.backup"

class StateManager:
    def __init__(self):
        self._ensure_data_dir()
        self.state = self._load_state()

    def _ensure_data_dir(self):
        if not os.path.exists("data"):
            os.makedirs("data")

    def _load_state(self):
        """Carga el estado, intentando restaurar desde backup si el archivo principal está corrupto."""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Estado principal corrupto o ilegible: {e}. Intentando restaurar desde backup...")
                # Intentar restaurar desde backup
                if os.path.exists(STATE_BACKUP):
                    try:
                        shutil.copy2(STATE_BACKUP, STATE_FILE)
                        logger.info("Estado restaurado desde backup exitosamente")
                        with open(STATE_FILE, "r", encoding="utf-8") as f:
                            return json.load(f)
                    except Exception as restore_error:
                        logger.error(f"Error restaurando desde backup: {restore_error}")
                logger.warning("Iniciando con estado vacío debido a corrupción")
                return {}
        return {}

    def save_state(self):
        """
        Guarda el estado de forma atómica para evitar corrupción.
        Crea backup antes de escribir y usa archivo temporal.
        """
        try:
            # Crear backup si existe el archivo original
            if os.path.exists(STATE_FILE):
                try:
                    shutil.copy2(STATE_FILE, STATE_BACKUP)
                except Exception as e:
                    logger.warning(f"No se pudo crear backup: {e}")
            
            # Escribir a archivo temporal primero
            temp_file = STATE_FILE + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
            
            # Renombrar atómicamente (operación atómica en la mayoría de sistemas)
            os.replace(temp_file, STATE_FILE)
            
        except Exception as e:
            logger.error(f"Error guardando estado: {e}")
            # Intentar restaurar desde backup si existe
            if os.path.exists(STATE_BACKUP):
                try:
                    shutil.copy2(STATE_BACKUP, STATE_FILE)
                    logger.info("Estado restaurado desde backup")
                except Exception as restore_error:
                    logger.error(f"Error restaurando backup: {restore_error}")
            raise

    def get_last_update_id(self):
        return self.state.get("_telegram", {}).get("last_update_id")

    def set_last_update_id(self, update_id: int):
        if "_telegram" not in self.state:
            self.state["_telegram"] = {}
        self.state["_telegram"]["last_update_id"] = int(update_id)
        self.save_state()

    def set_pending_quiz(self, page_id: str, page_title: str, quiz: dict, sent_at_ts: float):
        """
        Stores the latest quiz as pending evaluation with session timeout (1 hour).
        """
        if "_pending" not in self.state:
            self.state["_pending"] = {}
        
        # Crear estructura de sesión con respuestas
        session_id = f"session_{int(sent_at_ts)}"
        self.state["_pending"]["quiz"] = {
            "page_id": page_id,
            "title": page_title,
            "sent_at": sent_at_ts,
            "expires_at": sent_at_ts + 3600,  # 1 hora = 3600 segundos
            "session_id": session_id,
            "quiz": quiz,
            "answers": {},  # {question_number: {"text": "...", "timestamp": ...}}
            "completed": False
        }
        self.save_state()
        return session_id
    
    def add_answer_to_session(self, question_number: int, answer_text: str, timestamp: float):
        """Agrega una respuesta a la sesión activa."""
        pending = self.get_pending_quiz()
        if not pending:
            return False
        
        if "answers" not in pending:
            pending["answers"] = {}
        
        pending["answers"][str(question_number)] = {
            "text": answer_text,
            "timestamp": timestamp
        }
        self.save_state()
        return True
    
    def is_session_expired(self, pending: dict) -> bool:
        """Verifica si la sesión expiró (más de 1 hora)."""
        if not pending:
            return True
        expires_at = pending.get("expires_at", 0)
        return time.time() > expires_at
    
    def get_session_answers(self) -> dict:
        """Obtiene las respuestas de la sesión activa."""
        pending = self.get_pending_quiz()
        if not pending:
            return {}
        return pending.get("answers", {})

    def get_pending_quiz(self):
        return self.state.get("_pending", {}).get("quiz")

    def clear_pending_quiz(self):
        if "_pending" in self.state and "quiz" in self.state["_pending"]:
            del self.state["_pending"]["quiz"]
            self.save_state()

    def record_performance(self, page_id: str, page_title: str, level: str, user_text: str, evaluation: dict):
        """
        level: bajo|medio|alto
        """
        today = datetime.now().strftime("%Y-%m-%d")

        if page_id not in self.state:
            self.state[page_id] = {
                "title": page_title,
                "reviews": 0,
                "mastery_level": "novice",
                "history": [],
            }

        if "performance" not in self.state[page_id]:
            self.state[page_id]["performance"] = []

        self.state[page_id]["performance"].append(
            {
                "date": today,
                "level": level,
                "user_text": user_text,
                "evaluation": evaluation,
            }
        )

        # Calcular mastery_level basado en historial (últimas 5 evaluaciones)
        self._update_mastery_level(page_id)

        self.save_state()
    
    def _update_mastery_level(self, page_id: str):
        """
        Actualiza mastery_level basado en el historial de rendimiento.
        Considera las últimas 5 evaluaciones para determinar el nivel.
        """
        if page_id not in self.state:
            return
        
        perf = self.state[page_id].get("performance", [])
        if not perf:
            self.state[page_id]["mastery_level"] = "novice"
            return
        
        # Considerar últimas 5 evaluaciones
        recent_perf = perf[-5:]
        
        # Contar niveles
        alto_count = sum(1 for p in recent_perf if p.get("level") == "alto")
        medio_count = sum(1 for p in recent_perf if p.get("level") == "medio")
        bajo_count = sum(1 for p in recent_perf if p.get("level") == "bajo")
        
        total = len(recent_perf)
        
        # Calcular porcentajes
        alto_pct = alto_count / total if total > 0 else 0
        medio_pct = medio_count / total if total > 0 else 0
        
        # Determinar nivel basado en tendencia
        if alto_pct >= 0.6:  # 60% o más alto
            self.state[page_id]["mastery_level"] = "advanced"
        elif alto_pct + medio_pct >= 0.6:  # 60% o más alto+medio
            self.state[page_id]["mastery_level"] = "intermediate"
        else:
            self.state[page_id]["mastery_level"] = "novice"

    def mark_page_reviewed(self, page_id, page_title):
        today = datetime.now().strftime("%Y-%m-%d")
        
        if page_id not in self.state:
            self.state[page_id] = {
                "title": page_title,
                "reviews": 0,
                "mastery_level": "novice",
                "history": []
            }
        
        self.state[page_id]["last_reviewed"] = today
        self.state[page_id]["reviews"] += 1
        self.state[page_id]["history"].append(today)
        self.save_state()

    def get_page_state(self, page_id):
        return self.state.get(page_id, None)

    def is_reviewed_recently(self, page_id, days_cooldown=1):
        """Check if page was reviewed in the last N days."""
        page_data = self.state.get(page_id)
        if not page_data or "last_reviewed" not in page_data:
            return False
            
        last_date = datetime.strptime(page_data["last_reviewed"], "%Y-%m-%d")
        delta = (datetime.now() - last_date).days
        return delta < days_cooldown
