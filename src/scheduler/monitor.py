from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger
import random
import asyncio
from typing import Dict
from src.auth.moodle_auth import MoodleAuthenticator
from src.auth.session_manager import SessionManager
from src.scraper.tc_parser import TCPageParser
from src.scraper.slot_detector import SlotDetector
from src.booking.auto_booker import AutoBooker
from src.booking.slot_transfer import SlotTransfer
from src.notifications.telegram_notifier import TelegramNotifier
from src.notifications.telegram_listener import TelegramListener
from src.utils.exceptions import SessionExpiredError, TCBotException
from src.config.settings import Settings


class TCMonitor:
    """Monitor seeker TC and handle slot transfers"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.scheduler = AsyncIOScheduler()
        self.authenticator = MoodleAuthenticator(settings.moodle_url)
        self.detector = SlotDetector()
        self.booked_tc_ids = set()
        self.currently_holding_slot = None

        saved_session = SessionManager.load_session(settings.session_cache_file)
        if saved_session:
            self.authenticator.session = saved_session
            if self.authenticator.is_authenticated():
                logger.info("Restored session from cache")
            else:
                logger.info("Cached session invalid, will re-authenticate")
                self._authenticate()
        else:
            self._authenticate()

        self.parser = TCPageParser(self.authenticator.session)
        self.booker = AutoBooker(self.authenticator.session, self.parser)
        self.transfer = SlotTransfer(self.authenticator.session, self.parser, self.booker)

        self.notifier = TelegramNotifier(
            settings.telegram_bot_token,
            settings.telegram_chat_id
        )
        self.listener = TelegramListener(
            settings.telegram_bot_token,
            settings.telegram_chat_id
        )

    def _authenticate(self):
        """Authenticate with Moodle"""
        self.authenticator.login(self.settings.moodle_username, self.settings.moodle_password)
        SessionManager.save_session(self.authenticator.session, self.settings.session_cache_file)

    def start(self):
        """Start monitoring seeker TC"""
        # Start Telegram listener in background
        asyncio.create_task(self.listener.start_listening())

        # Add seeker monitoring job if configured
        if self.settings.seeker:
            jitter = random.randint(-5, 5)
            interval = max(30, self.settings.seeker.check_interval + jitter)

            self.scheduler.add_job(
                self.check_seeker_tc,
                trigger=IntervalTrigger(seconds=interval),
                id="seeker_monitor",
                max_instances=1
            )
            logger.info(f"Added seeker monitoring job for {self.settings.seeker.test_name} (interval: {interval}s)")
        else:
            # Fallback to old multi-TC monitoring for backwards compatibility
            for tc in self.settings.tc_pages:
                jitter = random.randint(-5, 5)
                interval = max(30, tc.check_interval + jitter)

                self.scheduler.add_job(
                    self.check_tc_page,
                    trigger=IntervalTrigger(seconds=interval),
                    args=[tc],
                    id=f"tc_{tc.id}",
                    max_instances=1
                )
                logger.info(f"Added monitoring job for {tc.name} (interval: {interval}s)")

        self.scheduler.start()

    async def check_tc_page(self, tc_config):
        """
        Check single TC page for availability

        Steps:
        1. Check if already booked for this TC → stop monitoring if yes
        2. Verify session authenticated
        3. Fetch TC page
        4. Parse available slots
        5. Filter by date/time ranges from config
        6. Detect new slots (matching preferences)
        7. Book first matching slot
        8. Send notification
        9. Stop monitoring this TC (mark as booked)
        10. Handle errors (re-authenticate if session expired)
        """
        if tc_config.id in self.booked_tc_ids:
            logger.debug(f"TC {tc_config.name} already booked, skipping")
            return

        try:
            logger.debug(f"Checking TC page: {tc_config.name}")

            if not self.authenticator.is_authenticated():
                logger.warning("Session expired, re-authenticating")
                self._authenticate()
                self.parser.session = self.authenticator.session
                self.booker.session = self.authenticator.session

            soup = self.parser.fetch_tc_page(tc_config.url)

            if self.parser.is_already_booked(soup):
                logger.info(f"Already booked for {tc_config.name}, stopping monitoring")
                self.booked_tc_ids.add(tc_config.id)
                self._remove_monitoring_job(tc_config.id)
                return

            all_slots = self.parser.get_available_slots(soup)

            filtered_slots = self.detector.filter_slots_by_preferences(all_slots, tc_config)

            new_slots = self.detector.detect_new_slots(tc_config.id, filtered_slots)

            if new_slots:
                logger.info(f"Found {len(new_slots)} new matching slots for {tc_config.name}")
                await self.notifier.notify_slot_found(tc_config.name, new_slots)

                for slot in new_slots:
                    try:
                        success = self.booker.book_slot(tc_config.url, slot)

                        if success:
                            logger.success(f"Successfully booked slot: {slot['date']} {slot['time']}")
                            await self.notifier.notify_booking_success(tc_config.name, slot)
                            self.booked_tc_ids.add(tc_config.id)
                            self._remove_monitoring_job(tc_config.id)
                            break
                        else:
                            logger.warning(f"Failed to book slot: {slot['date']} {slot['time']}")
                            await self.notifier.notify_booking_failure(tc_config.name, slot, "Booking failed")

                    except Exception as e:
                        logger.error(f"Error booking slot: {e}")
                        await self.notifier.notify_booking_failure(tc_config.name, slot, str(e))

        except SessionExpiredError:
            logger.warning("Session expired during check, will re-authenticate on next run")
            self._authenticate()
            self.parser.session = self.authenticator.session
            self.booker.session = self.authenticator.session

        except TCBotException as e:
            logger.error(f"Bot error checking {tc_config.name}: {e}")
            await self.notifier.notify_error(f"Error checking {tc_config.name}: {e}")

        except Exception as e:
            logger.exception(f"Unexpected error checking {tc_config.name}: {e}")
            await self.notifier.notify_error(f"Unexpected error: {e}")

    def _remove_monitoring_job(self, tc_id: str):
        """Remove monitoring job for a TC"""
        job_id = f"tc_{tc_id}"
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed monitoring job {job_id}")
        except Exception as e:
            logger.warning(f"Could not remove job {job_id}: {e}")

    async def check_seeker_tc(self):
        """
        Check seeker TC for available slots

        Steps:
        1. Check if currently holding a slot in seeker (skip if yes)
        2. Verify session authenticated
        3. Fetch seeker TC page
        4. Parse available slots for seeker test section
        5. Filter by date/time preferences
        6. Detect new slots
        7. If new slot found:
           a. Book it in seeker TC
           b. Mark as currently_holding_slot
           c. Send Telegram asking for target TC
           d. Trigger transfer workflow (background task)
        """
        if self.currently_holding_slot:
            logger.debug("Already holding slot, waiting for transfer")
            return

        try:
            logger.debug(f"Checking seeker TC: {self.settings.seeker.test_name}")

            if not self.authenticator.is_authenticated():
                logger.warning("Session expired, re-authenticating")
                self._authenticate()
                self.parser.session = self.authenticator.session
                self.booker.session = self.authenticator.session
                self.transfer.session = self.authenticator.session

            soup = self.parser.fetch_tc_page(self.settings.seeker.tc_url)

            # Check if already registered (shouldn't be, but double-check)
            if self.parser.is_registered_for_test(soup, self.settings.seeker.test_name):
                logger.warning("Seeker TC already registered - this shouldn't happen")
                return

            # Get available slots for seeker test
            available_slots = self.parser.get_available_slots_for_test(soup, self.settings.seeker.test_name)

            # Filter by preferences
            filtered_slots = self.detector.filter_slots_by_preferences(
                available_slots,
                self.settings.seeker
            )

            # Detect new slots
            new_slots = self.detector.detect_new_slots("seeker", filtered_slots)

            if new_slots:
                # Book first matching slot
                slot = new_slots[0]
                logger.info(f"Found matching slot in seeker: {slot['date']} {slot['time']}")

                success = self.booker.register_slot(slot['register_url'])

                if success:
                    self.currently_holding_slot = slot
                    logger.success(f"Booked slot in seeker TC: {slot['date']} {slot['time']}")

                    # Ask user for target TC
                    target_tc_names = [tc.name for tc in self.settings.target_tcs]
                    await self.notifier.notify_slot_found_and_booked(
                        self.settings.seeker.test_name,
                        slot,
                        target_tc_names
                    )

                    # Start transfer workflow in background
                    asyncio.create_task(self.handle_slot_transfer(slot))

        except SessionExpiredError:
            logger.warning("Session expired during check, will re-authenticate on next run")
            self._authenticate()
            self.parser.session = self.authenticator.session
            self.booker.session = self.authenticator.session
            self.transfer.session = self.authenticator.session

        except TCBotException as e:
            logger.error(f"Bot error checking seeker TC: {e}")
            await self.notifier.notify_error(f"Error checking seeker: {e}")

        except Exception as e:
            logger.exception(f"Unexpected error checking seeker TC: {e}")
            await self.notifier.notify_error(f"Unexpected error: {e}")

    async def handle_slot_transfer(self, slot: Dict):
        """
        Handle slot transfer workflow

        Steps:
        1. Wait for user's Telegram response (target TC)
        2. Parse response to get target TC URL
        3. Execute transfer
        4. Send confirmation
        5. Clear currently_holding_slot
        """
        try:
            # Wait for user response (1 hour timeout)
            response = await self.listener.wait_for_target_tc_response(timeout=3600)

            target_tc_url = self.listener.parse_target_tc(response, self.settings.target_tcs)

            # Find target TC name for logging
            target_tc_name = next(
                (tc.name for tc in self.settings.target_tcs if tc.url == target_tc_url),
                target_tc_url
            )

            await self.notifier.notify_transfer_started(target_tc_name)

            # Execute transfer
            success = self.transfer.transfer_slot(
                seeker_tc_url=self.settings.seeker.tc_url,
                seeker_test_name=self.settings.seeker.test_name,
                target_tc_url=target_tc_url,
                slot_date=slot['date'],
                slot_time=slot['time']
            )

            if success:
                await self.notifier.notify_transfer_success(target_tc_name, slot)
                logger.success(f"Successfully transferred slot to {target_tc_name}")
            else:
                await self.notifier.notify_transfer_failed(target_tc_name, "Transfer failed")
                logger.error(f"Transfer to {target_tc_name} failed")

        except asyncio.TimeoutError:
            await self.notifier.notify_error("Transfer timeout - no response received in 1 hour")
            logger.warning("Transfer timeout - slot may still be in seeker")

        except Exception as e:
            await self.notifier.notify_error(f"Transfer error: {e}")
            logger.exception(f"Error during transfer: {e}")

        finally:
            self.currently_holding_slot = None

    def stop(self):
        """Graceful shutdown"""
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")

        # Stop Telegram listener
        try:
            asyncio.create_task(self.listener.stop_listening())
        except Exception as e:
            logger.warning(f"Error stopping Telegram listener: {e}")
