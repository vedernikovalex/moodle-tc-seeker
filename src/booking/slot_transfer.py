import requests
from bs4 import BeautifulSoup
from loguru import logger
from src.utils.exceptions import BookingError
from src.scraper.tc_parser import TCPageParser
from src.booking.auto_booker import AutoBooker
from typing import Dict, Optional
from datetime import datetime


class SlotTransfer:
    """Handle slot transfer from seeker to target TC"""

    def __init__(self, session: requests.Session, parser: TCPageParser, booker: AutoBooker):
        self.session = session
        self.parser = parser
        self.booker = booker

    def transfer_slot(self, seeker_tc_url: str, seeker_test_name: str, target_tc_url: str, slot_date: str, slot_time: str) -> bool:
        """
        Transfer slot from seeker TC to target TC

        Args:
            seeker_tc_url: URL of seeker TC
            seeker_test_name: Name of seeker test section
            target_tc_url: URL of target TC
            slot_date: Date in format YYYY-MM-DD (e.g., "2026-01-20")
            slot_time: Time in format HH:MM (e.g., "15:50")

        Returns:
            True if transfer successful, False otherwise

        Steps:
        1. Get seeker TC page, extract unregister URL for the slot
        2. Get target TC page
        3. Check if target TC has same date/time slot available
        4. If target already registered, unregister first
        5. Register for new slot in target TC
        6. Unregister from seeker TC (free it up)
        7. Verify entire transfer succeeded
        """
        try:
            logger.info(f"Starting slot transfer: {slot_date} {slot_time} from seeker to target")

            # Step 1: Get seeker TC page and extract unregister URL
            seeker_soup = self.parser.fetch_tc_page(seeker_tc_url)
            seeker_reserved = self.parser.get_reserved_slots_for_test(seeker_soup, seeker_test_name)

            if not seeker_reserved:
                logger.error("No reserved slot found in seeker TC")
                return False

            seeker_slot = seeker_reserved[0]
            seeker_unregister_url = seeker_slot['unregister_url']

            logger.info(f"Found seeker slot: {seeker_slot['date']} {seeker_slot['time']}")

            # Step 2: Get target TC page
            target_soup = self.parser.fetch_tc_page(target_tc_url)

            # Step 3: Find matching slot in target TC
            # Note: We need to determine the test name for target TC
            # For now, assume it's the first test section on the page
            # TODO: Make this configurable or smarter
            matching_slot = self.find_matching_slot_in_target(target_soup, slot_date, slot_time)

            if not matching_slot:
                logger.error(f"No matching slot found in target TC for {slot_date} {slot_time}")
                return False

            logger.info(f"Found matching slot in target TC")

            # Step 4: Check if target already has a registration
            # For simplicity, assume target has same test structure
            # In production, you'd need to identify which test section to check
            target_test_sections = self._extract_test_sections(target_soup)
            target_has_registration = False
            target_unregister_url = None

            for test_section in target_test_sections:
                reserved = self.parser.get_reserved_slots_for_test(target_soup, test_section)
                if reserved:
                    target_has_registration = True
                    target_unregister_url = reserved[0]['unregister_url']
                    logger.info(f"Target TC already has registration, will unregister first")
                    break

            # Step 5: Unregister from target if needed
            if target_has_registration:
                success = self.booker.unregister_slot(target_unregister_url)
                if not success:
                    logger.error("Failed to unregister from target TC")
                    return False
                logger.info("Unregistered from target TC")

            # Step 6: Register for new slot in target TC
            success = self.booker.register_slot(matching_slot['register_url'])
            if not success:
                logger.error("Failed to register new slot in target TC")
                return False
            logger.info("Registered new slot in target TC")

            # Step 7: Unregister from seeker TC (free it up)
            success = self.booker.unregister_slot(seeker_unregister_url)
            if not success:
                logger.warning("Failed to unregister from seeker TC - slot may still be reserved")
                # Don't fail the transfer - target registration succeeded

            logger.success(f"Slot transfer completed successfully: {slot_date} {slot_time}")
            return True

        except Exception as e:
            logger.error(f"Error during slot transfer: {e}")
            raise BookingError(f"Failed to transfer slot: {e}")

    def find_matching_slot_in_target(self, target_soup: BeautifulSoup, date: str, time: str) -> Optional[Dict]:
        """
        Find slot with matching date/time in target TC available slots

        Args:
            target_soup: BeautifulSoup object of target TC page
            date: Date in format YYYY-MM-DD
            time: Time in format HH:MM

        Returns:
            Slot dict if found, None if not available
        """
        try:
            # Get all test sections from target
            test_sections = self._extract_test_sections(target_soup)

            # For each test section, check for available slots
            for test_name in test_sections:
                try:
                    available_slots = self.parser.get_available_slots_for_test(target_soup, test_name)

                    for slot in available_slots:
                        if slot['date'] == date and slot['time'] == time:
                            logger.info(f"Found matching slot in test section: {test_name}")
                            return slot

                except Exception as e:
                    logger.warning(f"Error checking test section {test_name}: {e}")
                    continue

            return None

        except Exception as e:
            logger.error(f"Error finding matching slot in target: {e}")
            return None

    def _extract_test_sections(self, soup: BeautifulSoup) -> list:
        """
        Extract test section names from TC page

        Returns:
            List of test names (e.g., ["Zápočtový test", "Teoretický zkouškový test ZS 2025"])
        """
        try:
            test_names = []

            # Find all h3 tags that contain test names
            headers = soup.find_all('h3')

            for header in headers:
                text = header.get_text(strip=True)
                # Check if it starts with "Test:"
                if text.startswith('Test:'):
                    # Extract the test name (after "Test:")
                    test_name_link = header.find('a')
                    if test_name_link:
                        test_name = test_name_link.get_text(strip=True)
                        test_names.append(test_name)

            logger.debug(f"Found {len(test_names)} test sections: {test_names}")
            return test_names

        except Exception as e:
            logger.error(f"Error extracting test sections: {e}")
            return []
