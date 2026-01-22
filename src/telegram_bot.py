import os
import asyncio
import html
from telegram import Bot
from telegram.constants import ParseMode

class TelegramSender:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if not self.token or not self.chat_id:
            raise ValueError("TELEGRAM credentials not found")
        self.bot = Bot(token=self.token)

    async def send_quiz(self, topic, quiz_data, session_id=None):
        """
        Sends the formatted quiz to the user using HTML mode for safety.
        """
        safe_topic = html.escape(topic)
        safe_session = html.escape(str(session_id or 'N/A'))
        
        header = (
            f"📚 <b>Hora de Estudio: {safe_topic}</b> 📚\n\n"
            f"Aquí tienes tu ronda de 6 preguntas.\n\n"
            f"💡 <b>Instrucciones:</b>\n"
            f"• Responde cada pregunta numerada (ej: '1) mi respuesta')\n"
            f"• Tienes <b>1 hora</b> para responder\n"
            f"• Puedes responder todas o solo algunas\n"
            f"• Las respuestas se evaluarán automáticamente\n\n"
            f"⏰ <b>Sesión activa hasta:</b> {safe_session}"
        )
        await self.bot.send_message(chat_id=self.chat_id, text=header, parse_mode=ParseMode.HTML)

        question_number = 1
        
        # Sections
        question_number = await self._send_section("🟢 <b>Preguntas Básicas</b>", quiz_data.get("easy", []), question_number)
        question_number = await self._send_section("🟡 <b>Preguntas de Desarrollo</b>", quiz_data.get("development", []), question_number)
        question_number = await self._send_section("🔴 <b>Caso de Estudio</b>", quiz_data.get("case_study", []), question_number)
        
        # Mensaje final
        await self.bot.send_message(
            chat_id=self.chat_id,
            text="✅ <b>Quiz completo enviado</b>\n\nResponde con el formato: 'N) tu respuesta' donde N es el número de pregunta.",
            parse_mode=ParseMode.HTML
        )

    async def _send_section(self, title, questions, start_number=1):
        await self.bot.send_message(chat_id=self.chat_id, text=f"\n{title}", parse_mode=ParseMode.HTML)
        
        current_number = start_number
        for q in questions:
            safe_question = html.escape(q['question'])
            q_text = f"<b>{current_number}) {safe_question}</b>\n"
            
            if "options" in q:
                for opt in q["options"]:
                    safe_opt = html.escape(opt)
                    q_text += f"  {safe_opt}\n"
            
            # Send Question
            await self.bot.send_message(chat_id=self.chat_id, text=q_text, parse_mode=ParseMode.HTML)
            
            # Send Answer (Hidden as Spoiler)
            if "correct_option" in q:
                raw_ans = f"✅ Correcta: {q['correct_option']}\nℹ️ {q.get('explanation', '')}"
            else:
                raw_ans = f"💡 Respuesta sugerida: {q.get('answer', '')}"
            
            safe_ans = html.escape(raw_ans)
            spoiler = f'<span class="tg-spoiler">{safe_ans}</span>'
            
            try:
                await self.bot.send_message(chat_id=self.chat_id, text=spoiler, parse_mode=ParseMode.HTML)
            except Exception as e:
                print(f"Error sending answer: {e}")
            
            current_number += 1
            await asyncio.sleep(1) 
        
        return current_number
