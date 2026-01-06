from datetime import datetime, time as datetime_time, date as datetime_date
from loguru import logger
from typing import List, Dict
from src.config.settings import TCPageConfig


class SlotDetector:
    """Detect and filter available slots"""

    def __init__(self):
        self.previous_state = {}

    def filter_slots_by_preferences(self, slots: List[Dict], tc_config: TCPageConfig) -> List[Dict]:
        """
        Filter slots by date and time ranges

        Example:
        - Config: date_range: 2026-01-15 to 2026-01-20, time_range: 10:00-16:00
        - Slot: date=2026-01-18, time=14:00 → MATCH (book it)
        - Slot: date=2026-01-25, time=14:00 → REJECT (outside date range)
        - Slot: date=2026-01-18, time=08:00 → REJECT (outside time range)
        """
        filtered_slots = []

        try:
            start_date = datetime.strptime(tc_config.date_range.start, "%Y-%m-%d").date()
            end_date = datetime.strptime(tc_config.date_range.end, "%Y-%m-%d").date()
            start_time = datetime.strptime(tc_config.time_range.start, "%H:%M").time()
            end_time = datetime.strptime(tc_config.time_range.end, "%H:%M").time()

            for slot in slots:
                try:
                    slot_date = datetime.strptime(slot['date'], "%Y-%m-%d").date()
                    slot_time = datetime.strptime(slot['time'], "%H:%M").time()

                    if start_date <= slot_date <= end_date and start_time <= slot_time <= end_time:
                        filtered_slots.append(slot)
                        logger.debug(f"Slot matches preferences: {slot['date']} {slot['time']}")
                    else:
                        logger.debug(f"Slot rejected (outside preferences): {slot['date']} {slot['time']}")

                except (KeyError, ValueError) as e:
                    logger.warning(f"Error parsing slot data: {e}")
                    continue

        except (ValueError, AttributeError) as e:
            logger.error(f"Error parsing date/time ranges from config: {e}")
            return []

        logger.info(f"Filtered {len(filtered_slots)}/{len(slots)} slots matching preferences")
        return filtered_slots

    def detect_new_slots(self, tc_id: str, current_slots: List[Dict]) -> List[Dict]:
        """
        Compare current slots with previous state
        Return only NEW slots
        """
        if tc_id not in self.previous_state:
            self.previous_state[tc_id] = set()

        current_slot_ids = {self._get_slot_key(slot) for slot in current_slots}
        previous_slot_ids = self.previous_state[tc_id]

        new_slot_ids = current_slot_ids - previous_slot_ids

        new_slots = [slot for slot in current_slots if self._get_slot_key(slot) in new_slot_ids]

        self.previous_state[tc_id] = current_slot_ids

        if new_slots:
            logger.info(f"Detected {len(new_slots)} new slots for TC {tc_id}")
        else:
            logger.debug(f"No new slots detected for TC {tc_id}")

        return new_slots

    def _get_slot_key(self, slot: Dict) -> str:
        """Generate unique key for slot"""
        return f"{slot.get('date', '')}_{slot.get('time', '')}_{slot.get('slot_id', '')}"
