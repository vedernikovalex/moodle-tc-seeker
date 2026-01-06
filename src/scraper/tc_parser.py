import requests
from bs4 import BeautifulSoup
from loguru import logger
from src.utils.exceptions import ParsingError, SessionExpiredError
from typing import List, Dict, Optional
import re
from urllib.parse import urljoin, urlparse, parse_qs
from datetime import datetime, date


class TCPageParser:
    """Parse TC booking page structure"""

    def __init__(self, session: requests.Session):
        self.session = session

    def fetch_tc_page(self, tc_url: str) -> BeautifulSoup:
        """
        Fetch TC page with authenticated session
        Handle 303 redirects gracefully
        """
        try:
            response = self.session.get(tc_url, allow_redirects=True)

            if response.status_code == 303 or 'login/index.php' in response.url:
                logger.warning("Session expired - redirected to login page")
                raise SessionExpiredError("Session expired, need to re-authenticate")

            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'lxml')
            return soup

        except SessionExpiredError:
            raise
        except Exception as e:
            logger.error(f"Error fetching TC page: {e}")
            raise ParsingError(f"Failed to fetch TC page: {e}")

    def get_available_slots(self, soup: BeautifulSoup) -> List[Dict]:
        """
        Extract available slots from TC page

        NOTE: This implementation is a SKELETON and needs to be updated
        after manually inspecting the actual TC page HTML structure.

        Expected return format:
        [
            {
                'date': '2026-01-10',
                'time': '14:00',
                'slot_id': 'xyz123',
                'capacity': 1,
                'booking_url': 'https://...'
            }
        ]
        """
        logger.warning("get_available_slots needs implementation - HTML structure unknown")

        return []

    def is_already_booked(self, soup: BeautifulSoup) -> bool:
        """
        Check if user already has booking for this TC
        Parse HTML to find existing booking indicator

        NOTE: This implementation is a SKELETON and needs to be updated
        after manually inspecting the actual TC page HTML structure.
        """
        logger.warning("is_already_booked needs implementation - HTML structure unknown")

        return False

    def extract_booking_form_data(self, soup: BeautifulSoup, slot_id: str) -> Optional[Dict]:
        """
        Extract booking form details for a specific slot

        NOTE: This implementation is a SKELETON and needs to be updated
        after manually inspecting the actual TC page HTML structure.

        Expected return format:
        {
            'action_url': 'https://...',
            'slot_id': 'xyz123',
            'sesskey': 'abc...',
            'other_fields': {...}
        }
        """
        logger.warning("extract_booking_form_data needs implementation - HTML structure unknown")

        return None

    def get_available_dates(self, soup: BeautifulSoup, test_name: str) -> List[Dict]:
        """
        Parse calendar view for available dates

        Returns:
        [
            {
                'date': '2026-01-20',
                'day_link': '?id=776603&day=2026-01-20&quiz=801703#tc',
                'capacity': 456,
                'quiz_id': '801703'
            }
        ]
        """
        try:
            available_dates = []

            # Find all td elements with alert-success class (available dates)
            date_cells = soup.find_all('td', class_='alert-success')

            for cell in date_cells:
                link = cell.find('a')
                if not link:
                    continue

                href = link.get('href', '')
                if not href or 'day=' not in href:
                    continue

                # Extract date from URL parameter
                match = re.search(r'day=(\d{4}-\d{2}-\d{2})', href)
                if not match:
                    continue

                date_str = match.group(1)

                # Extract quiz_id
                quiz_match = re.search(r'quiz=(\d+)', href)
                quiz_id = quiz_match.group(1) if quiz_match else None

                # Extract capacity from text (format: "20 (456 🪑)")
                text = link.get_text(strip=True)
                capacity_match = re.search(r'\((\d+)\s*🪑\)', text)
                capacity = int(capacity_match.group(1)) if capacity_match else 0

                available_dates.append({
                    'date': date_str,
                    'day_link': href,
                    'capacity': capacity,
                    'quiz_id': quiz_id
                })

            logger.debug(f"Found {len(available_dates)} available dates")
            return available_dates

        except Exception as e:
            logger.error(f"Error parsing available dates: {e}")
            raise ParsingError(f"Failed to parse available dates: {e}")

    def get_available_times_for_date(self, date_url: str) -> List[Dict]:
        """
        Fetch and parse time slots for a specific date

        Args:
            date_url: Relative or absolute URL for the date (e.g., "?id=776603&day=2026-01-20&quiz=801703#tc")

        Returns:
        [
            {
                'time': '15:50',
                'register_url': 'https://moodle.czu.cz/mod/tcb/view.php?id=776603&quiz=801703&slot=413832#tc',
                'capacity': 10,
                'slot_id': '413832'
            }
        ]
        """
        try:
            # Make URL absolute if relative
            if date_url.startswith('?'):
                base_url = 'https://moodle.czu.cz/mod/tcb/view.php'
                full_url = base_url + date_url
            else:
                full_url = date_url

            # Fetch the time slots page
            soup = self.fetch_tc_page(full_url)

            available_times = []

            # Find all td elements with alert-success class (available time slots)
            time_cells = soup.find_all('td', class_='alert-success')

            for cell in time_cells:
                link = cell.find('a')
                if not link:
                    continue

                href = link.get('href', '')
                if not href or 'slot=' not in href:
                    continue

                # Extract slot_id
                slot_match = re.search(r'slot=(\d+)', href)
                if not slot_match:
                    continue

                slot_id = slot_match.group(1)

                # Extract time from text (format: "15:50 - rezervovat")
                text = link.get_text(strip=True)
                time_match = re.match(r'(\d{1,2}:\d{2})', text)
                if not time_match:
                    continue

                time_str = time_match.group(1)

                # Extract capacity (format: "(10 🪑)")
                capacity_text = cell.get_text(strip=True)
                capacity_match = re.search(r'\((\d+)\s*🪑\)', capacity_text)
                capacity = int(capacity_match.group(1)) if capacity_match else 0

                available_times.append({
                    'time': time_str,
                    'register_url': href,
                    'capacity': capacity,
                    'slot_id': slot_id
                })

            logger.debug(f"Found {len(available_times)} available time slots for date")
            return available_times

        except Exception as e:
            logger.error(f"Error parsing available times: {e}")
            raise ParsingError(f"Failed to parse available times: {e}")

    def get_reserved_slots_for_test(self, soup: BeautifulSoup, test_name: str) -> List[Dict]:
        """
        Extract reserved slots for specific test section
        Only returns slots with dates >= today (ignores past slots)

        Returns:
        [
            {
                'date': '15.01.2026',
                'time': '18:20',
                'unregister_url': 'https://moodle.czu.cz/mod/tcb/view.php?id=776603&unregister=407275#tc',
                'unregister_deadline': '15.01. 16:20'
            }
        ]
        """
        try:
            reserved_slots = []
            today = date.today()

            # Find all h3 tags with test names
            test_headers = soup.find_all('h3')

            for header in test_headers:
                # Check if this is the test we're looking for
                header_text = header.get_text(strip=True)
                if test_name not in header_text:
                    continue

                # Find the reserved slots table after this header
                # Look for h4 with "Vaše rezervované termíny"
                current = header.find_next_sibling()
                while current:
                    if current.name == 'h4' and 'rezervované termíny' in current.get_text().lower():
                        # Found reserved slots section
                        table = current.find_next('table')
                        if table:
                            rows = table.find_all('tr')[1:]  # Skip header row
                            for row in rows:
                                cells = row.find_all('td')
                                if len(cells) >= 5:
                                    date_str = cells[1].get_text(strip=True)
                                    time = cells[2].get_text(strip=True)

                                    # Parse Czech date format (DD.MM.YYYY)
                                    try:
                                        slot_date = datetime.strptime(date_str, '%d.%m.%Y').date()

                                        # Skip past dates
                                        if slot_date < today:
                                            logger.debug(f"Skipping past-date reserved slot: {date_str}")
                                            continue
                                    except ValueError:
                                        logger.warning(f"Could not parse date: {date_str}")
                                        continue

                                    # Extract unregister link
                                    unregister_link = cells[4].find('a')
                                    unregister_url = unregister_link.get('href', '') if unregister_link else ''

                                    # Extract deadline (format: "(do 15.01. 16:20)")
                                    deadline_text = cells[4].get_text(strip=True)
                                    deadline_match = re.search(r'\(do\s+([^)]+)\)', deadline_text)
                                    deadline = deadline_match.group(1) if deadline_match else ''

                                    reserved_slots.append({
                                        'date': date_str,
                                        'time': time,
                                        'unregister_url': unregister_url,
                                        'unregister_deadline': deadline
                                    })
                        break

                    # Move to next h3 (new test section)
                    if current.name == 'h3':
                        break

                    current = current.find_next_sibling()

            logger.debug(f"Found {len(reserved_slots)} future reserved slots for test: {test_name}")
            return reserved_slots

        except Exception as e:
            logger.error(f"Error parsing reserved slots: {e}")
            raise ParsingError(f"Failed to parse reserved slots: {e}")

    def is_registered_for_test(self, soup: BeautifulSoup, test_name: str) -> bool:
        """Check if user is registered for specific test section"""
        reserved_slots = self.get_reserved_slots_for_test(soup, test_name)
        return len(reserved_slots) > 0

    def get_available_slots_for_test(self, soup: BeautifulSoup, test_name: str) -> List[Dict]:
        """
        Extract all available slots for specific test section
        Combines date calendar + time slots for each date

        Returns:
        [
            {
                'date': '2026-01-20',
                'time': '15:50',
                'register_url': 'https://moodle.czu.cz/mod/tcb/view.php?id=776603&quiz=801703&slot=413832#tc',
                'capacity': 10,
                'slot_id': '413832'
            }
        ]
        """
        try:
            all_slots = []

            # Get available dates from calendar
            available_dates = self.get_available_dates(soup, test_name)

            logger.info(f"Fetching time slots for {len(available_dates)} available dates")

            # For each date, fetch time slots
            for date_info in available_dates:
                try:
                    times = self.get_available_times_for_date(date_info['day_link'])

                    for time_info in times:
                        all_slots.append({
                            'date': date_info['date'],
                            'time': time_info['time'],
                            'register_url': time_info['register_url'],
                            'capacity': time_info['capacity'],
                            'slot_id': time_info['slot_id']
                        })

                except Exception as e:
                    logger.warning(f"Error fetching times for date {date_info['date']}: {e}")
                    continue

            logger.info(f"Found {len(all_slots)} total available slots for test: {test_name}")
            return all_slots

        except Exception as e:
            logger.error(f"Error getting available slots: {e}")
            raise ParsingError(f"Failed to get available slots: {e}")
