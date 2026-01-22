import os
import asyncio
import time
import sys
import re
from dotenv import load_dotenv
from telegram.constants import ParseMode
from src.notion_adapter import NotionAdapter
from src.ai_generator import QuestionGenerator
from src.telegram_bot import TelegramSender
from src.state_manager import StateManager
from src.telegram_receiver import TelegramReceiver
from src.ai_evaluator import AnswerEvaluator
from src.web_search import WebSearch
from src.coach_logic import CoachLogic
from src.utils import logger, validate_quiz_structure

# Load env if running locally
load_dotenv()

# --- Helper Functions (Moved outside main) ---

async def _process_expired_session(state_manager, pending, evaluator):
    """Procesa una sesión expirada guardando respuestas parciales."""
    answers = pending.get("answers", {})
    if not answers:
        logger.info("Sesión expirada sin respuestas. Cerrando sesión.")
        return
    
    logger.info(f"Procesando sesión expirada con {len(answers)} respuestas parciales...")
    await _evaluate_and_save_answers(state_manager, pending, evaluator, answers, partial=True)


async def _process_completed_session(state_manager, pending, evaluator, answers):
    """Procesa una sesión completada (todas las respuestas o expirada)."""
    is_partial = len(answers) < 6
    logger.info(f"Procesando sesión {'parcial' if is_partial else 'completa'} con {len(answers)} respuestas...")
    await _evaluate_and_save_answers(state_manager, pending, evaluator, answers, partial=is_partial)


async def _evaluate_and_save_answers(state_manager, pending, evaluator, answers, partial=False):
    """Evalúa y guarda las respuestas (completas o parciales)."""
    quiz = pending.get("quiz", {})
    page_id = pending.get("page_id")
    page_title = pending.get("title", "Tema")
    
    # Combinar todas las respuestas en un texto para evaluación
    all_responses = []
    for q_num in sorted(answers.keys(), key=int):
        answer_data = answers[q_num]
        all_responses.append(f"Pregunta {q_num}: {answer_data.get('text', '')}")
    
    combined_text = "\n".join(all_responses)
    
    if not combined_text.strip():
        logger.warning("No hay respuestas válidas para evaluar")
        return
    
    try:
        # Evaluar respuestas combinadas
        evaluation = evaluator.evaluate_freeform(
            topic_title=page_title,
            quiz=quiz,
            user_answer_text=combined_text,
        )
        
        level = evaluation.get("level", "medio")
        
        # Ajustar nivel si es parcial (ser más conservador)
        if partial:
            if level == "alto":
                level = "medio"  # No puede ser "alto" si no respondió todo
            logger.info(f"Evaluación parcial: {len(answers)}/6 respuestas → nivel: {level}")
        
        # Guardar performance
        state_manager.record_performance(
            page_id=page_id,
            page_title=page_title,
            level=level,
            user_text=combined_text,
            evaluation=evaluation,
        )
        
        status = "parcial" if partial else "completa"
        logger.info(f"Performance guardada ({status}): {page_title} → {level}")
        
        # Notificar al usuario si es posible
        try:
            from src.telegram_bot import TelegramSender
            telegram = TelegramSender()
            status_msg = "parcial" if partial else "completa"
            await telegram.bot.send_message(
                chat_id=os.getenv("TELEGRAM_CHAT_ID"),
                text=(
                    f"✅ *Evaluación {status_msg}*\n\n"
                    f"Tema: {page_title}\n"
                    f"Respuestas: {len(answers)}/6\n"
                    f"Nivel: *{level.upper()}*\n\n"
                    f"{'⏰ Sesión expirada' if partial else '🎉 ¡Completaste todas las preguntas!'}"
                ),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.warning(f"No se pudo enviar notificación: {e}")
            
    except Exception as e:
        logger.error(f"Error evaluando respuestas: {e}")

# --- Main Routine ---

async def main():
    print("DEBUG: Entered main()")
    logger.info("--- Starting StudyBot Routine ---")
    
    # 1. Initialize Components
    state_manager = StateManager()
    try:
        print("DEBUG: Initializing components...", flush=True)
        print("DEBUG: - Notion...", flush=True)
        notion = NotionAdapter()
        print("DEBUG: - AI Generator...", flush=True)
        ai = QuestionGenerator()
        print("DEBUG: - Evaluator...", flush=True)
        evaluator = AnswerEvaluator()
        print("DEBUG: - TelegramSender...", flush=True)
        telegram = TelegramSender()
        print("DEBUG: - TelegramReceiver...", flush=True)
        receiver = TelegramReceiver()
        print("DEBUG: - WebSearch...", flush=True)
        web_search = WebSearch()
        print("DEBUG: - CoachLogic...", flush=True)
        coach = CoachLogic(state_manager)
        print("DEBUG: Initialization complete.", flush=True)
    except Exception as e:
        print(f"DEBUG: Error happened: {e}")
        logger.error(f"Initialization Failed: {e}")
        sys.exit(1)

    # 1.5 Process pending session
    print("DEBUG: Checking pending session...")
    pending = state_manager.get_pending_quiz()
    print(f"DEBUG: Pending session status: {bool(pending)}")
    
    if pending:
        logger.info("Sesión pendiente encontrada. Procesando respuestas...")
        
        # Verificar si la sesión expiró (1 hora)
        if state_manager.is_session_expired(pending):
            logger.info("Sesión expirada (más de 1 hora). Cerrando y guardando respuestas parciales...")
            await _process_expired_session(state_manager, pending, evaluator)
            state_manager.clear_pending_quiz()
        else:
            # Sesión aún activa, procesar nuevas respuestas
            try:
                last_update_id = state_manager.get_last_update_id()
                new_msgs = receiver.get_new_messages(last_update_id, allowed_chat_id=os.getenv("TELEGRAM_CHAT_ID"))

                if new_msgs:
                    max_update = max(m["update_id"] for m in new_msgs)
                    state_manager.set_last_update_id(max_update)
                    
                # Procesar mensajes que llegaron después del quiz
                sent_at = pending.get("sent_at") or 0
                processed_answers = False
                
                for msg in new_msgs:
                    if not msg.get("text") or not msg.get("date"):
                        continue
                    
                    msg_timestamp = float(msg.get("date", 0))
                    if msg_timestamp < sent_at:
                        continue
                    
                    # Intentar parsear respuesta (formato: "N) respuesta" o "N. respuesta")
                    text = msg["text"].strip()
                    match = re.match(r'^(\d+)[).]\s*(.+)$', text, re.DOTALL)
                    
                    if match:
                        question_num = int(match.group(1))
                        answer_text = match.group(2).strip()
                        
                        # Validar que el número de pregunta sea válido (1-9)
                        if 1 <= question_num <= 9:
                            state_manager.add_answer_to_session(question_num, answer_text, msg_timestamp)
                            logger.info(f"Respuesta registrada para pregunta {question_num}")
                            processed_answers = True
                
                # Si hay respuestas nuevas, verificar si se completó o si expiró
                if processed_answers:
                    answers = state_manager.get_session_answers()
                    total_questions = 6
                    answered_count = len(answers)
                    
                    logger.info(f"Progreso: {answered_count}/{total_questions} preguntas respondidas")
                    
                    # Si se respondieron todas o expiró, procesar
                    if answered_count >= total_questions or state_manager.is_session_expired(pending):
                        await _process_completed_session(state_manager, pending, evaluator, answers)
                        state_manager.clear_pending_quiz()
                    else:
                        # Aún hay tiempo y faltan respuestas
                        time_remaining = pending.get("expires_at", 0) - time.time()
                        minutes_left = int(time_remaining / 60)
                        if minutes_left > 0:
                            logger.info(f"Sesión activa. Faltan {total_questions - answered_count} respuestas. Tiempo restante: {minutes_left} minutos")
                else:
                    logger.info("No new answers found for pending session.")
                
            except Exception as e:
                logger.error(f"Error procesando sesión pendiente: {e}")
                # Continuar con el flujo normal aunque falle el procesamiento


    # 2. Fetch Candidates
    print("DEBUG: Entering Step 2 (Fetch Pages)")
    logger.info("Fetching pages from Notion...")
    try:
        pages = notion.fetch_all_pages()
        logger.info(f"Found {len(pages)} pages.")
    except Exception as e:
        logger.error(f"Error obteniendo páginas de Notion: {e}")
        return

    if not pages:
        logger.warning("No pages found. Check permissions.")
        return

    # 3. Select Topic (usando lógica de coaching inteligente)
    logger.info("Seleccionando tema usando lógica de coaching inteligente...")
    selected = coach.select_best_topic(pages)
    
    if not selected:
        logger.warning("No se pudo seleccionar tema. Abortando.")
        return
    
    chosen_page = selected["page"]
    chosen_page_id = selected["id"]
    title = selected["title"]
    
    logger.info(f"Tema seleccionado: {title} (score: {selected['score']:.2f})")

    # 4. Get Content
    try:
        content = notion.get_page_content(chosen_page_id, max_depth=5)
    except Exception as e:
        logger.error(f"Error obteniendo contenido de página: {e}")
        return
    
    if not content:
        logger.warning("Page is empty. Skipping.")
        return
    
    logger.info(f"Content length: {len(content)} chars.")

    # 4.5 Get Coaching Context (historial, gaps, temas relacionados)
    page_state = state_manager.get_page_state(chosen_page_id) or {}
    personalized_instructions = coach.get_personalized_instructions(chosen_page_id, page_state)
    related_topics_context = coach.get_related_topics_context(pages, chosen_page_id)
    
    if personalized_instructions:
        logger.info("Instrucciones personalizadas generadas basadas en historial")
    if related_topics_context:
        logger.info("Contexto de temas relacionados identificado")

    # 4.6 Enrich with Web Search (con fallback graceful si falla)
    logger.info("Enriching context with web search...")
    try:
        enriched_context = web_search.get_enriched_context(title, content, max_web_chars=2000)
        logger.info(f"Enriched context length: {len(enriched_context)} chars.")
    except Exception as e:
        logger.warning(f"Error en búsqueda web, usando solo contenido de Notion: {e}")
        enriched_context = content  # Fallback seguro

    # 5. Generate Quiz (con personalización inteligente)
    logger.info("Generating personalized questions...")
    try:
        quiz = ai.generate_questions(
            title, 
            content, 
            enriched_context=enriched_context,
            personalized_instructions=personalized_instructions,
            related_topics_context=related_topics_context
        )
    except Exception as e:
        logger.error(f"Error generando quiz: {e}")
        return
    
    if not quiz:
        logger.error("Failed to generate quiz.")
        return

    # 5.5 Validate Quiz Structure
    is_valid, error_msg = validate_quiz_structure(quiz)
    if not is_valid:
        logger.error(f"Quiz inválido: {error_msg}")
        logger.error(f"Quiz recibido: {quiz}")
        return

    # 6. Send to Telegram (con sesión de 1 hora)
    logger.info("Sending to Telegram...")
    sent_at_ts = time.time()
    try:
        session_id = state_manager.set_pending_quiz(chosen_page_id, title, quiz, sent_at_ts)
        await telegram.send_quiz(title, quiz, session_id=session_id)
    except Exception as e:
        logger.error(f"Error enviando quiz a Telegram: {e}")
        return

    # 7. Update State (crítico - debe guardarse siempre)
    try:
        state_manager.mark_page_reviewed(chosen_page_id, title)
        # El pending_quiz ya se guardó en el paso 6 con session_id
        logger.info("Done! State saved successfully.")
    except Exception as e:
        logger.error(f"Error crítico guardando estado: {e}")
        # No hacer return aquí porque el quiz ya se envió - mejor dejar que continúe

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot interrumpido por el usuario")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error fatal: {e}")
        sys.exit(1)
