from telegram.ext import Application, MessageHandler, filters
from loguru import logger
import asyncio
from src.config.settings import TargetTC
from typing import List


class TelegramListener:
    """Listen for user responses to bot messages"""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.pending_response = None
        self.response_queue = asyncio.Queue()
        self.application = None

    async def start_listening(self):
        """
        Start Telegram bot polling for messages

        This runs indefinitely in the background
        """
        try:
            logger.info("Starting Telegram listener")

            self.application = Application.builder().token(self.bot_token).build()

            # Add message handler for text messages
            self.application.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
            )

            # Initialize the application
            await self.application.initialize()
            await self.application.start()

            # Start polling for updates
            await self.application.updater.start_polling(drop_pending_updates=True)

            # Keep running (polling runs in background)
            logger.info("Telegram listener started successfully")

        except Exception as e:
            logger.error(f"Error in Telegram listener: {e}")
            raise

    async def stop_listening(self):
        """Stop the Telegram bot"""
        if self.application:
            try:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
                logger.info("Telegram listener stopped")
            except Exception as e:
                logger.warning(f"Error stopping Telegram listener: {e}")

    async def handle_message(self, update, context):
        """
        Handle incoming Telegram message

        Args:
            update: Telegram update object
            context: Telegram context
        """
        try:
            # Check if message is from the correct chat
            if str(update.message.chat_id) != str(self.chat_id):
                logger.debug(f"Ignoring message from chat {update.message.chat_id}")
                return

            message_text = update.message.text
            logger.info(f"Received Telegram message: {message_text}")

            # Check what type of response we're expecting
            if self.pending_response == "target_tc":
                await self.response_queue.put({
                    'type': 'target_tc',
                    'value': message_text
                })
                logger.debug("Queued target TC response")
            else:
                logger.debug("No pending response expected, ignoring message")

        except Exception as e:
            logger.error(f"Error handling Telegram message: {e}")

    async def wait_for_target_tc_response(self, timeout: int = 3600) -> str:
        """
        Wait for user to reply with target TC

        Args:
            timeout: Timeout in seconds (default 1 hour)

        Returns:
            TC URL or name from user response

        Raises:
            asyncio.TimeoutError if no response within timeout
        """
        self.pending_response = "target_tc"
        logger.info(f"Waiting for target TC response (timeout: {timeout}s)")

        try:
            response = await asyncio.wait_for(
                self.response_queue.get(),
                timeout=timeout
            )
            logger.info(f"Received target TC response: {response['value']}")
            return response['value']

        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for target TC response")
            raise

        finally:
            self.pending_response = None

    def parse_target_tc(self, response: str, target_tcs: List[TargetTC]) -> str:
        """
        Parse user response to extract TC URL

        Handles:
        - Direct URL: "https://moodle.czu.cz/mod/tcb/view.php?id=XXXXXX"
        - TC name: "UNIX Exam"
        - Number: "1" (index in target_tcs list)

        Args:
            response: User's text response
            target_tcs: List of configured target TCs

        Returns:
            TC URL

        Raises:
            ValueError if response cannot be parsed
        """
        response = response.strip()

        # Check if it's a URL
        if response.startswith("http"):
            logger.info(f"Parsed as direct URL: {response}")
            return response

        # Check if it's a number (index)
        try:
            index = int(response) - 1
            if 0 <= index < len(target_tcs):
                tc_url = target_tcs[index].url
                logger.info(f"Parsed as index {response}: {target_tcs[index].name} ({tc_url})")
                return tc_url
        except ValueError:
            pass

        # Check if it matches a TC name (case-insensitive partial match)
        for tc in target_tcs:
            if tc.name.lower() in response.lower() or response.lower() in tc.name.lower():
                logger.info(f"Parsed as TC name: {tc.name} ({tc.url})")
                return tc.url

        # Could not parse
        error_msg = f"Could not parse target TC from response: '{response}'"
        logger.error(error_msg)
        raise ValueError(error_msg)
