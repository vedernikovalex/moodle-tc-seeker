import requests
from bs4 import BeautifulSoup
from loguru import logger
from src.utils.exceptions import BookingError
from src.scraper.tc_parser import TCPageParser
from typing import Dict, Optional


class AutoBooker:
    """Automatically book available slots"""

    def __init__(self, session: requests.Session, parser: TCPageParser):
        self.session = session
        self.parser = parser

    def book_slot(self, tc_url: str, slot: Dict) -> bool:
        """
        Attempt to book a specific slot

        Steps:
        1. Fetch TC page to get booking form
        2. Extract booking form action URL and parameters
        3. Prepare POST data with slot_id and CSRF tokens
        4. Submit booking request
        5. Verify booking success
        6. Return success status

        NOTE: This implementation is a SKELETON and needs to be updated
        after manually inspecting the actual TC page HTML structure.
        """
        try:
            logger.info(f"Attempting to book slot: {slot.get('date')} {slot.get('time')}")

            soup = self.parser.fetch_tc_page(tc_url)

            form_data = self.parser.extract_booking_form_data(soup, slot.get('slot_id'))

            if not form_data:
                logger.error("Could not extract booking form data")
                raise BookingError("Failed to extract booking form data")

            logger.warning("book_slot needs implementation - booking form structure unknown")

            return False

        except Exception as e:
            logger.error(f"Error booking slot: {e}")
            raise BookingError(f"Failed to book slot: {e}")

    def verify_booking(self, tc_url: str, slot: Dict) -> bool:
        """
        Verify booking was successful

        NOTE: This implementation is a SKELETON and needs to be updated
        after manually inspecting the actual TC page HTML structure.
        """
        logger.warning("verify_booking needs implementation - verification method unknown")

        return False

    def register_slot(self, register_url: str) -> bool:
        """
        Register for a slot using registration URL

        Args:
            register_url: Full or relative registration URL
                         (e.g., "https://moodle.czu.cz/mod/tcb/view.php?id=776603&quiz=801703&slot=413832#tc")

        Returns:
            True if registration successful, False otherwise
        """
        try:
            # Make URL absolute if relative
            if register_url.startswith('?'):
                base_url = 'https://moodle.czu.cz/mod/tcb/view.php'
                full_url = base_url + register_url
            else:
                full_url = register_url

            logger.info(f"Attempting to register slot via: {full_url}")

            # Simply GET the registration URL
            # The onclick="confirmTC()" confirmation is handled automatically
            response = self.session.get(full_url, allow_redirects=True)

            if response.status_code != 200:
                logger.error(f"Registration request failed with status {response.status_code}")
                return False

            # Parse response to verify registration
            soup = BeautifulSoup(response.text, 'lxml')

            # Check for success indicators
            # Look for "Rezervovaný termín" in the page
            if 'Rezervovaný termín' in response.text or 'rezervovaný termín' in response.text.lower():
                logger.success("Slot registration successful")
                return True

            # Check for error messages
            error_divs = soup.find_all('div', class_='alert-danger')
            if error_divs:
                error_msg = error_divs[0].get_text(strip=True)
                logger.error(f"Registration failed: {error_msg}")
                return False

            # If no clear indicators, assume success if status was 200
            logger.warning("Registration status unclear, assuming success based on HTTP 200")
            return True

        except Exception as e:
            logger.error(f"Error registering slot: {e}")
            raise BookingError(f"Failed to register slot: {e}")

    def unregister_slot(self, unregister_url: str) -> bool:
        """
        Unregister from a slot using unregister URL

        Args:
            unregister_url: Full or relative unregister URL
                           (e.g., "https://moodle.czu.cz/mod/tcb/view.php?id=776603&unregister=407275#tc")

        Returns:
            True if unregistration successful, False otherwise
        """
        try:
            # Make URL absolute if relative
            if unregister_url.startswith('?'):
                base_url = 'https://moodle.czu.cz/mod/tcb/view.php'
                full_url = base_url + unregister_url
            elif not unregister_url.startswith('http'):
                full_url = 'https://moodle.czu.cz' + unregister_url
            else:
                full_url = unregister_url

            logger.info(f"Attempting to unregister slot via: {full_url}")

            # Simply GET the unregister URL
            response = self.session.get(full_url, allow_redirects=True)

            if response.status_code != 200:
                logger.error(f"Unregister request failed with status {response.status_code}")
                return False

            # Parse response to verify unregistration
            soup = BeautifulSoup(response.text, 'lxml')

            # Check for success indicators
            # Look for success messages or confirmation text
            if 'byl odhlášen' in response.text.lower() or 'úspěšně odhlášen' in response.text.lower():
                logger.success("Slot unregistration successful (confirmation message found)")
                return True

            # Check for error messages
            error_divs = soup.find_all('div', class_='alert-danger')
            if error_divs:
                error_msg = error_divs[0].get_text(strip=True)
                logger.error(f"Unregistration failed: {error_msg}")
                return False

            # If no error message and request succeeded, assume success
            # (the page might redirect and show other test sections with reserved slots)
            logger.success("Slot unregistration successful (HTTP 200, no errors)")
            return True

        except Exception as e:
            logger.error(f"Error unregistering slot: {e}")
            raise BookingError(f"Failed to unregister slot: {e}")
