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

    def transfer_slot(self, seeker_tc_url: str, seeker_test_name: str, target_tc_url: str, slot_date: str, slot_time: str, target_test_name: Optional[str] = None) -> bool:
        """
        Transfer slot from seeker TC to target TC

        Args:
            seeker_tc_url: URL of seeker TC
            seeker_test_name: Name of seeker test section
            target_tc_url: URL of target TC
            slot_date: Date in format YYYY-MM-DD (e.g., "2026-01-20")
            slot_time: Time in format HH:MM (e.g., "15:50")
            target_test_name: Specific test section name to transfer to (REQUIRED)

        Returns:
            True if transfer successful, False otherwise

        Steps:
        1. Get seeker TC page, extract unregister URL and slot details
        2. Get target TC page, check if already registered (unregister if yes)
        3. Build target registration URL for the same date/time
        4. UNREGISTER from seeker TC (frees up that time slot globally)
        5. IMMEDIATELY register in target TC (race to grab the now-free time slot!)

        Note: We DON'T check if slot is available in target beforehand because
        the user is currently occupying that TIME via seeker (can't be in two places at once).
        Once we unregister from seeker, that time becomes free and available in target.
        """
        try:
            logger.info(f"Starting slot transfer: {slot_date} {slot_time} from seeker to target test: {target_test_name}")

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

            # Step 3: Check if already registered in SPECIFIC test section only
            logger.info(f"Checking for existing registration in test section: {target_test_name}")
            target_reserved = self.parser.get_reserved_slots_for_test(target_soup, target_test_name)

            if target_reserved:
                target_unregister_url = target_reserved[0]['unregister_url']
                logger.info(f"Target TC already has registration for {target_test_name}, unregistering first")

                success = self.booker.unregister_slot(target_unregister_url)
                if not success:
                    logger.error("Failed to unregister from target TC")
                    return False
                logger.info("Unregistered from target TC")

            # Step 4: Build target registration URL for same date/time as seeker
            # NOTE: We trust that once we free up seeker, this time will be available in target
            logger.info(f"Preparing to transfer to target TC at {slot_date} {slot_time}")

            # We need to find the registration URL for this date/time in target
            # But we can't check availability while occupying this time in seeker
            # So we'll check AFTER unregistering from seeker

            # Step 5: CRITICAL - Unregister from seeker to free up the time slot
            logger.info("Unregistering from seeker TC to free up time slot...")
            success = self.booker.unregister_slot(seeker_unregister_url)
            if not success:
                logger.error("Failed to unregister from seeker TC - cannot proceed with transfer")
                return False
            logger.success("Unregistered from seeker TC - time slot now free")

            # Step 6: IMMEDIATELY check for and register in target TC
            # Re-fetch target page to see available slots (now that time is free)
            logger.info("Re-fetching target TC to find newly available slot...")
            target_soup = self.parser.fetch_tc_page(target_tc_url)

            matching_slot = self.find_exact_slot_in_target(target_soup, slot_date, slot_time, target_test_name)

            if not matching_slot:
                logger.error(f"CRITICAL: Slot {slot_date} {slot_time} not available in target TC!")
                logger.error("Unregistered from seeker but couldn't register in target - check manually")
                return False

            logger.info(f"Found available slot in target TC, registering immediately...")
            success = self.booker.register_slot(matching_slot['register_url'])
            if not success:
                logger.error("CRITICAL: Failed to register in target TC after unregistering from seeker!")
                logger.error("You may have lost the slot - check manually")
                return False
            logger.success("Successfully registered in target TC")

            logger.success(f"Slot transfer completed successfully: {slot_date} {slot_time}")
            return True

        except Exception as e:
            logger.error(f"Error during slot transfer: {e}")
            raise BookingError(f"Failed to transfer slot: {e}")

    def find_exact_slot_in_target(self, target_soup: BeautifulSoup, date: str, time: str, test_name: str) -> Optional[Dict]:
        """
        Efficiently check if exact date/time slot is available in target TC
        WITHOUT fetching all dates and times (much faster)

        Args:
            target_soup: BeautifulSoup object of target TC page
            date: Date in format YYYY-MM-DD (e.g., "2026-01-10")
            time: Time in format HH:MM (e.g., "13:50")
            test_name: Specific test section name

        Returns:
            Slot dict with register_url if found, None if not available
        """
        try:
            logger.info(f"Checking if slot {date} {time} is available in test section: {test_name}")

            # Step 1: Check if the date is available in the calendar
            available_dates = self.parser.get_available_dates(target_soup, test_name)

            matching_date = None
            for date_info in available_dates:
                if date_info['date'] == date:
                    matching_date = date_info
                    break

            if not matching_date:
                logger.warning(f"Date {date} not available in calendar")
                return None

            logger.debug(f"Date {date} is available, checking time slots...")

            # Step 2: Fetch ONLY the time slots for this specific date
            times = self.parser.get_available_times_for_date(matching_date['day_link'])

            # Step 3: Check if the exact time is available
            for time_info in times:
                if time_info['time'] == time:
                    logger.success(f"Found exact matching slot: {date} {time}")
                    return {
                        'date': date,
                        'time': time,
                        'register_url': time_info['register_url'],
                        'capacity': time_info['capacity'],
                        'slot_id': time_info['slot_id']
                    }

            logger.warning(f"Time {time} not available for date {date}")
            return None

        except Exception as e:
            logger.error(f"Error finding exact slot in target: {e}")
            return None

    def find_matching_slot_in_target(self, target_soup: BeautifulSoup, date: str, time: str, target_test_name: Optional[str] = None) -> Optional[Dict]:
        """
        DEPRECATED: Use find_exact_slot_in_target() instead for better performance

        Find slot with matching date/time in target TC available slots

        Args:
            target_soup: BeautifulSoup object of target TC page
            date: Date in format YYYY-MM-DD
            time: Time in format HH:MM
            target_test_name: Specific test section name to search in (optional)

        Returns:
            Slot dict if found, None if not available
        """
        try:
            # Get test sections to search
            if target_test_name:
                # Search only the specified test section
                test_sections = [target_test_name]
                logger.info(f"Searching for slot in specific test section: {target_test_name}")
            else:
                # Search all test sections
                test_sections = self._extract_test_sections(target_soup)
                logger.info(f"Searching for slot in all test sections")

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
