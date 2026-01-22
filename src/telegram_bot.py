import os
import asyncio
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
        Sends the formatted quiz to the user.
        Formato permite responder pregunta por pregunta.
        """
        header = (
            f"📚 *Hora de Estudio: {topic}* 📚\n\n"
            f"Aquí tienes tu ronda de 6 preguntas.\n\n"
            f"💡 *Instrucciones:*\n"
            f"• Responde cada pregunta numerada (ej: '1) mi respuesta')\n"
            f"• Tienes *1 hora* para responder\n"
            f"• Puedes responder todas o solo algunas\n"
            f"• Las respuestas se evaluarán automáticamente\n\n"
            f"⏰ *Sesión activa hasta:* {session_id or 'N/A'}"
        )
        await self.bot.send_message(chat_id=self.chat_id, text=header, parse_mode=ParseMode.MARKDOWN)

        question_number = 1
        
        # 1. Easy Questions
        question_number = await self._send_section("🟢 *Preguntas Básicas*", quiz_data.get("easy", []), question_number)
        
        # 2. Development Questions
        question_number = await self._send_section("🟡 *Preguntas de Desarrollo*", quiz_data.get("development", []), question_number)

        # 3. Case Study
        question_number = await self._send_section("🔴 *Caso de Estudio*", quiz_data.get("case_study", []), question_number)
        
        # Mensaje final
        await self.bot.send_message(
            chat_id=self.chat_id,
            text="✅ *Quiz completo enviado*\n\nResponde con el formato: 'N) tu respuesta' donde N es el número de pregunta.",
            parse_mode=ParseMode.MARKDOWN
        )

    async def _send_section(self, title, questions, start_number=1):
        await self.bot.send_message(chat_id=self.chat_id, text=f"\n{title}", parse_mode=ParseMode.MARKDOWN)
        
        current_number = start_number
        for q in questions:
            q_text = f"*{current_number}) {q['question']}*\n"
            
            if "options" in q:
                for opt in q["options"]:
                    q_text += f"  {opt}\n"
            
            # Send Question
            await self.bot.send_message(chat_id=self.chat_id, text=q_text, parse_mode=ParseMode.MARKDOWN)
            
            # Send Answer (Hidden as Spoiler)
            answer_text = ""
            if "correct_option" in q:
                answer_text = f"✅ Correcta: {q['correct_option']}\nℹ️ {q.get('explanation', '')}"
            else:
                answer_text = f"💡 Respuesta sugerida: {q.get('answer', '')}"
            
            # Escape for MarkdownV2
            safe_answer = self._escape_markdown_v2(answer_text)
            spoiler = f"||{safe_answer}||"
            
            try:
                await self.bot.send_message(chat_id=self.chat_id, text=spoiler, parse_mode=ParseMode.MARKDOWN_V2)
            except Exception as e:
                print(f"Error sending answer: {e}")
            
            current_number += 1
            await asyncio.sleep(1) # Prevent flood limits
        
        return current_number

    def _escape_markdown_v2(self, text):
        """Helper to escape MarkdownV2 characters."""
        reserved = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in reserved:
            text = text.replace(char, f"\\{char}")
        return text
