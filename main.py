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
from src.content_processor import ContentProcessor
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
        
        # Ajustar nivel si es parcial
        if partial:
            if level == "alto": level = "medio"
            logger.info(f"Evaluación parcial: {len(answers)}/6 respuestas → nivel: {level}")
        
        # Guardar performance (si es notion page_id, sino loguear)
        if page_id and not page_id.startswith("DIRECT_"):
            state_manager.record_performance(
                page_id=page_id,
                page_title=page_title,
                level=level,
                user_text=combined_text,
                evaluation=evaluation,
            )
        else:
            logger.info("Skipping Notion performance save for direct content.")
        
        status = "parcial" if partial else "completa"
        logger.info(f"Performance guardada ({status}): {page_title} → {level}")
        
        # Notificar al usuario
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

async def _process_incoming_content(msg: dict, processor: ContentProcessor, receiver: TelegramReceiver) -> tuple[str, str]:
    """Processes a message containing a file or URL and returns (title, content)."""
    text = msg.get("text", "")
    document = msg.get("document")
    
    title = "Contenido Enviado"
    content = ""
    
    if document:
        # Process PDF
        file_id = document["file_id"]
        file_name = document["file_name"]
        logger.info(f"Processing PDF: {file_name}")
        
        file_bytes = await receiver.download_file_content(file_id)
        extracted_text = processor.extract_text_from_pdf(file_bytes)
        
        if extracted_text:
            content = extracted_text
            title = file_name
        else:
            logger.warning("No text extracted from PDF")
            
    elif text:
        # Check for URL
        url = processor.find_url_in_text(text)
        if url:
            logger.info(f"Processing URL: {url}")
            extracted_text = processor.extract_text_from_url(url)
            if extracted_text:
                content = extracted_text
                title = f"Web: {url}"
            else:
                logger.warning("No text extracted from URL")
    
    return title, content

# --- Main Routine ---

async def main():
    print("DEBUG: Entered main()")
    logger.info("--- Starting StudyBot Routine ---")
    
    # 1. Initialize Components
    state_manager = StateManager()
    
    try:
        print("DEBUG: Initializing components...", flush=True)
        notion = NotionAdapter()
        ai = QuestionGenerator()
        evaluator = AnswerEvaluator()
        telegram = TelegramSender()
        receiver = TelegramReceiver()
        web_search = WebSearch()
        coach = CoachLogic(state_manager)
        processor = ContentProcessor()
        print("DEBUG: Initialization complete.", flush=True)
    except Exception as e:
        print(f"DEBUG: Error happened: {e}")
        logger.error(f"Initialization Failed: {e}")
        sys.exit(1)

    # 2. Get New Messages (Single Source of Truth)
    last_update_id = state_manager.get_last_update_id()
    new_msgs = await receiver.get_new_messages(last_update_id, allowed_chat_id=os.getenv("TELEGRAM_CHAT_ID"))
    
    if new_msgs:
        max_update = max(m["update_id"] for m in new_msgs)
        state_manager.set_last_update_id(max_update)
        logger.info(f"Fetched {len(new_msgs)} new messages.")
    
    # 3. Classify Messages
    answer_msgs = []
    content_msgs = []
    
    for msg in new_msgs:
        text = msg.get("text", "")
        document = msg.get("document")
        
        # Check for URL in text
        has_url = "http" in text if text else False
        
        if document or has_url:
            content_msgs.append(msg)
        else:
            # Assume it's an answer if it's just text
            answer_msgs.append(msg)

    # 4. Handle Direct Content (Highest Priority)
    if content_msgs:
        target_msg = content_msgs[-1] # Process the latest one
        logger.info("New content detected! Processing...")
        
        title, content = await _process_incoming_content(target_msg, processor, receiver)
        
        if content and len(content) > 100:
            logger.info(f"Content extracted successfully ({len(content)} chars). Generating quiz...")
            
            # Generar Quiz
            try:
                # LIMITAR CONTENIDO para no explotar el contexto de la IA
                # REDUCCIÓN DRÁSTICA: 15k caracteres (aprox 3.7k tokens) para asegurar velocidad y evitar timeouts.
                safe_content = content[:15000]
                logger.info(f"Enviando {len(safe_content)} caracteres a la IA...")
                
                # Tell AI this is direct content
                instructions = "IMPORTANTE: El usuario ha enviado este documento especificamente. Genera preguntas BASADAS EXCLUSIVAMENTE en este texto."
                
                quiz = ai.generate_questions(
                    title, 
                    safe_content, 
                    enriched_context=safe_content, # Use content as context
                    personalized_instructions=instructions
                )
                
                if quiz:
                    is_valid, error_msg = validate_quiz_structure(quiz)
                    if is_valid:
                        # Send to Telegram
                        sent_at_ts = time.time()
                        # Use a special prefix for page_id to avoid Notion confusion
                        pseudo_id = f"DIRECT_{int(sent_at_ts)}"
                        
                        session_id = state_manager.set_pending_quiz(pseudo_id, title, quiz, sent_at_ts)
                        await telegram.send_quiz(title, quiz, session_id=session_id)
                        logger.info("Quiz from direct content sent!")
                        return # Exit after handling content
                    else:
                        logger.error(f"Invalid quiz generated: {error_msg}")
            except Exception as e:
                logger.error(f"Error generating quiz from content: {e}")
        else:
            logger.warning("Content too short or empty. Ignoring.")

    # 5. Handle Pending Session (Answers)
    pending = state_manager.get_pending_quiz()
    
    if pending:
        if state_manager.is_session_expired(pending):
            logger.info("Session expired. Closing.")
            await _process_expired_session(state_manager, pending, evaluator)
            state_manager.clear_pending_quiz()
            pending = None
        else:
            # Process answers from answer_msgs
            processed_answers = False
            sent_at = pending.get("sent_at") or 0
            
            for msg in answer_msgs:
                msg_timestamp = float(msg.get("date", 0))
                if msg_timestamp < sent_at: continue
                
                text = msg.get("text", "").strip()
                match = re.match(r'^(\d+)[).]\s*(.+)$', text, re.DOTALL)
                
                if match:
                    q_num = int(match.group(1))
                    a_text = match.group(2).strip()
                    if 1 <= q_num <= 6: # Now we have 6 questions
                        state_manager.add_answer_to_session(q_num, a_text, msg_timestamp)
                        processed_answers = True
            
            if processed_answers:
                answers = state_manager.get_session_answers()
                total = 6
                if len(answers) >= total:
                    await _process_completed_session(state_manager, pending, evaluator, answers)
                    state_manager.clear_pending_quiz()
                    return # Done
                else:
                    logger.info(f"Session active. Answers: {len(answers)}/{total}.")
                    return # Wait for more
            
            # If session is pending, we don't start a new Notion one
            logger.info("Session pending. Waiting for answers.")
            return

    # 6. Fallback: Notion Logic (Only if no content and no pending session)
    print("DEBUG: Entering Notion Logic")
    logger.info("Fetching pages from Notion...")
    try:
        pages = notion.fetch_all_pages()
    except Exception as e:
        logger.error(f"Error Notion: {e}")
        return

    if not pages:
        logger.warning("No pages found.")
        return

    # Select Topic
    selected = coach.select_best_topic(pages)
    if not selected: return
    
    chosen_page_id = selected["id"]
    title = selected["title"]
    logger.info(f"Tema seleccionado: {title}")

    # Get Content
    content = notion.get_page_content(chosen_page_id, max_depth=5)
    if not content: return

    # Context & Enrich
    page_state = state_manager.get_page_state(chosen_page_id) or {}
    personalized = coach.get_personalized_instructions(chosen_page_id, page_state)
    related = coach.get_related_topics_context(pages, chosen_page_id)
    
    try:
        enriched = web_search.get_enriched_context(title, content, max_web_chars=2000)
    except:
        enriched = content

    # Generate
    quiz = ai.generate_questions(title, content, enriched_context=enriched, personalized_instructions=personalized, related_topics_context=related)
    
    if quiz:
        is_valid, _ = validate_quiz_structure(quiz)
        if is_valid:
            sent_at_ts = time.time()
            session_id = state_manager.set_pending_quiz(chosen_page_id, title, quiz, sent_at_ts)
            await telegram.send_quiz(title, quiz, session_id=session_id)
            try:
                state_manager.mark_page_reviewed(chosen_page_id, title)
            except: pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error fatal: {e}")
        sys.exit(1)
