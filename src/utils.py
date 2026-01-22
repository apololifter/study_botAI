"""
Utilidades compartidas: retry logic, validación, logging.
"""
import time
import logging
import functools
from typing import Callable, Any, Optional, Tuple

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def retry_on_failure(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Decorador para agregar retry logic con exponential backoff.
    
    Args:
        max_attempts: Número máximo de intentos
        delay: Delay inicial en segundos
        backoff: Factor de multiplicación para el delay
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            current_delay = delay
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts:
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt}/{max_attempts}): {e}. "
                            f"Retrying in {current_delay}s..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"{func.__name__} failed after {max_attempts} attempts: {e}")
            
            # Si llegamos aquí, todos los intentos fallaron
            raise last_exception
        
        return wrapper
    return decorator


def validate_quiz_structure(quiz: dict) -> Tuple[bool, Optional[str]]:
    """
    Valida que el quiz tenga la estructura correcta con 6 preguntas (2+2+2).
    
    Args:
        quiz: Diccionario con el quiz generado
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not isinstance(quiz, dict):
        return False, "Quiz debe ser un diccionario"
    
    required_sections = ["easy", "development", "case_study"]
    for section in required_sections:
        if section not in quiz:
            return False, f"Falta sección requerida: {section}"
        
        if not isinstance(quiz[section], list):
            return False, f"Sección {section} debe ser una lista"
        
        if len(quiz[section]) != 2:
            return False, f"Sección {section} debe tener exactamente 2 preguntas, tiene {len(quiz[section])}"
        
        # Validar que cada pregunta tenga 'question' y 'answer'
        for i, q in enumerate(quiz[section]):
            if not isinstance(q, dict):
                return False, f"Pregunta {i+1} en {section} debe ser un diccionario"
            if "question" not in q:
                return False, f"Pregunta {i+1} en {section} falta campo 'question'"
            if "answer" not in q:
                return False, f"Pregunta {i+1} en {section} falta campo 'answer'"
    
    return True, None
