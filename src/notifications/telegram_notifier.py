from telegram import Bot
from telegram.error import TelegramError
from loguru import logger
from src.utils.exceptions import NotificationError
from typing import List, Dict


class TelegramNotifier:
    """Send notifications via Telegram"""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot = Bot(token=bot_token)
        self.chat_id = chat_id

    async def send_notification(self, message: str):
        """Send plain text message"""
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode='HTML')
            logger.debug(f"Telegram notification sent: {message[:50]}...")
        except TelegramError as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            raise NotificationError(f"Telegram error: {e}")

    async def notify_slot_found(self, tc_name: str, slots: List[Dict]):
        """Formatted notification for available slots"""
        slot_list = "\n".join([f"  - {s['date']} {s['time']}" for s in slots])
        message = f"""
New TC slot(s) available

<b>Subject:</b> {tc_name}
<b>Slots found:</b>
{slot_list}

<b>Status:</b> Attempting to book...
"""
        await self.send_notification(message)

    async def notify_booking_success(self, tc_name: str, slot: Dict):
        """Formatted notification for successful booking"""
        message = f"""
Booking successful

<b>Subject:</b> {tc_name}
<b>Date:</b> {slot.get('date', 'Unknown')}
<b>Time:</b> {slot.get('time', 'Unknown')}
<b>Status:</b> Confirmed
"""
        await self.send_notification(message)

    async def notify_booking_failure(self, tc_name: str, slot: Dict, error: str):
        """Formatted notification for booking failure"""
        message = f"""
Booking failed

<b>Subject:</b> {tc_name}
<b>Date:</b> {slot.get('date', 'Unknown')}
<b>Time:</b> {slot.get('time', 'Unknown')}
<b>Error:</b> {error}
"""
        await self.send_notification(message)

    async def notify_error(self, error: str):
        """Formatted notification for system errors"""
        message = f"""
System error

<b>Error:</b> {error}
"""
        await self.send_notification(message)

    async def notify_monitoring_started(self, tc_count: int):
        """Notification when monitoring starts"""
        message = f"""
TC Monitoring Bot started

<b>Monitoring {tc_count} TC page(s)</b>

Bot will check for available slots and book them automatically.
"""
        await self.send_notification(message)

    async def notify_slot_found_and_booked(self, test_name: str, slot: Dict, target_tc_names: List[str]):
        """
        Notify that seeker found and booked a slot
        Ask user which TC to transfer to

        Args:
            test_name: Name of seeker test
            slot: Slot dict with 'date' and 'time'
            target_tc_names: List of target TC names
        """
        slot_list = "\n".join([f"{i+1}. {name}" for i, name in enumerate(target_tc_names)])

        message = f"""
<b>Found and booked slot in Seeker TC</b>

<b>Test:</b> {test_name}
<b>Date:</b> {slot.get('date', 'Unknown')}
<b>Time:</b> {slot.get('time', 'Unknown')}

<b>Which TC should I transfer this to?</b>
Reply with:
{slot_list}

Or reply with TC URL
"""
        await self.send_notification(message)

    async def notify_transfer_started(self, target_tc_name: str):
        """Notify that transfer process started"""
        message = f"""
<b>Transfer started</b>

<b>Target TC:</b> {target_tc_name}

<b>Status:</b> Processing transfer...
"""
        await self.send_notification(message)

    async def notify_transfer_success(self, target_tc_name: str, slot: Dict):
        """Notify that transfer completed successfully"""
        message = f"""
<b>Transfer successful</b>

<b>Target TC:</b> {target_tc_name}
<b>Date:</b> {slot.get('date', 'Unknown')}
<b>Time:</b> {slot.get('time', 'Unknown')}

<b>Status:</b> Confirmed
Seeker TC has been freed for next search.
"""
        await self.send_notification(message)

    async def notify_transfer_failed(self, target_tc_name: str, error: str):
        """Notify that transfer failed"""
        message = f"""
<b>Transfer failed</b>

<b>Target TC:</b> {target_tc_name}
<b>Error:</b> {error}

<b>Status:</b> Please check manually
"""
        await self.send_notification(message)

    async def ask_which_test_section(self, test_sections: List[str]):
        """
        Ask user which test section to use

        Args:
            test_sections: List of test section names
        """
        section_list = "\n".join([f"{i+1}. {name}" for i, name in enumerate(test_sections)])

        message = f"""
<b>Multiple test sections found</b>

Which test section should I use?
{section_list}

Reply with the number (1, 2, etc.)
"""
        await self.send_notification(message)
