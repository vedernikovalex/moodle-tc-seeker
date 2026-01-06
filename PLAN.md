# Moodle TC Slot Seeker & Transfer Bot - Implementation Plan

## Overview

Automated Python bot that monitors a "seeker" TC for available slots, books them temporarily, then transfers them to a target TC based on user input via Telegram.

## User's Workflow Requirements

### Phase 1: Monitoring & Booking Seeker TC
1. **Seeker TC** (Zápočtový test section on URL `https://moodle.czu.cz/mod/tcb/view.php?id=776603`)
   - Monitors for available slots matching date/time preferences
   - Remains UNREGISTERED except when temporarily holding a found slot
   - When matching slot found → book it immediately in seeker TC

### Phase 2: User Notification & Response
2. **Telegram Notification**
   - Bot sends: "Found and booked slot [date/time] in Seeker TC. Which TC should I transfer it to? Reply with TC URL or subject name."
   - Bot waits for user's Telegram response
   - User replies with target TC URL (e.g., `https://moodle.czu.cz/mod/tcb/view.php?id=XXXXXX`) or subject name

### Phase 3: Slot Transfer
3. **Execute Transfer**
   - Parse user's response to get target TC URL
   - Navigate to target TC
   - Unregister from current slot (if already registered)
   - Book the new slot (same date/time as seeker slot)
   - Unregister from seeker TC (frees it up for next search)
   - Send confirmation to Telegram

## TC Page Structure Analysis

### Current Observations (from tc_page.html)

**Page Structure**:
- Single TC page can have MULTIPLE test sections (identified saw 2: "Teoretický zkouškový test ZS 2025" and "Zápočtový test")
- Each test section has:
  - Test name: `<h3>Test: <a href="...">TestName</a></h3>`
  - Reserved slots table: `<h4>Vaše rezervované termíny do Testovacího centra na tento test</h4>`
  - Available slots section: `<h4>Možnosti přihlášení do Testovacího centra na test...</h4>`

**Registered Slot Structure**:
```html
<table class="table table-bordered table-responsive">
  <tr>
    <th></th>
    <th>datum</th>
    <th>čas</th>
    <th>přijďte v</th>
    <th>stav / akce</th>
  </tr>
  <tr>
    <td>Rezervovaný termín:</td>
    <td>15.01.2026</td>
    <td>18:20</td>
    <td>18:10</td>
    <td>
      <strong>
        <a href="https://moodle.czu.cz/mod/tcb/view.php?id=776603&amp;unregister=407275#tc">
          odhlásit se
        </a>
      </strong>
      (do 15.01. 16:20)
    </td>
  </tr>
</table>
```

**Key Elements**:
- Unregister link: `href="...?id=776603&unregister=407275#tc"`
- Unregister deadline: `(do 15.01. 16:20)` - "until 15.01. 16:20"
- Date format: `DD.MM.YYYY`
- Time format: `HH:MM`

**Already Registered Alert**:
```html
<div class="alert alert-danger">
  Aktuálně se nemůžete hlásit na další termíny, protože máte termín rezervovaný...
</div>
```

### Available Slots Structure (CONFIRMED)

**Two-Step Booking Process**:

**Step 1: Calendar View** (dates)
```html
<td class="alert alert-success">
  <strong>
    <a href="?id=776603&amp;day=2026-01-20&amp;quiz=801703#tc">
      20 (456 🪑)
    </a>
  </strong>
</td>
```
- Link format: `?id=776603&day=YYYY-MM-DD&quiz=QUIZ_ID#tc`
- Capacity shown: `(456 🪑)` = 456 seats available for that date
- Class `alert alert-success` indicates available dates
- Class `alert alert-secondary` indicates unavailable dates

**Step 2: Time Slots View** (for specific date)
```html
<td class="alert alert-success">
  <strong>
    <a href="https://moodle.czu.cz/mod/tcb/view.php?id=776603&amp;quiz=801703&amp;slot=413832#tc" onclick="confirmTC()">
      15:50 - rezervovat
    </a>
  </strong>
  (10 🪑)
</td>
```
- Registration link format: `https://moodle.czu.cz/mod/tcb/view.php?id=776603&quiz=QUIZ_ID&slot=SLOT_ID#tc`
- Time format: `HH:MM - rezervovat` (rezervovat = reserve/book)
- Has `onclick="confirmTC()"` - confirmation dialog (already handled in HTML)
- Capacity per slot: `(10 🪑)` = 10 seats for this specific time
- Class `alert alert-success` indicates available time slots

## Architecture Changes from Original Plan

### What Changes

**ORIGINAL PLAN** (no longer applicable):
- Monitor multiple independent TCs
- Auto-book first matching slot
- Stop monitoring once booked
- No cross-TC interaction

**NEW PLAN**:
- Monitor ONLY seeker TC
- Book slot in seeker (temporary hold)
- Interactive Telegram conversation for target selection
- Transfer slot from seeker to target TC
- Continuous operation (seeker never stops monitoring)

### What Stays the Same

- Moodle authentication system
- Session management
- Date/time filtering logic
- Telegram notifications (expanded functionality)
- Error handling and logging

## Updated Project Structure

```
moodle-scrape/
├── src/
│   ├── auth/
│   │   ├── moodle_auth.py       # [KEEP] Authentication
│   │   └── session_manager.py   # [KEEP] Session persistence
│   ├── scraper/
│   │   ├── tc_parser.py         # [UPDATE] Parse TC pages, detect specific test sections
│   │   └── slot_detector.py     # [UPDATE] Filter slots, detect section-specific bookings
│   ├── booking/
│   │   ├── auto_booker.py       # [UPDATE] Book slots, unregister slots
│   │   └── slot_transfer.py     # [NEW] Transfer slot logic
│   ├── notifications/
│   │   ├── telegram_notifier.py # [UPDATE] Interactive Telegram conversation
│   │   └── telegram_listener.py # [NEW] Listen for user responses
│   ├── scheduler/
│   │   └── monitor.py           # [MAJOR UPDATE] New monitoring logic
│   ├── config/
│   │   └── settings.py          # [UPDATE] New config structure
│   └── utils/
│       ├── logger.py            # [KEEP] Logging
│       └── exceptions.py        # [KEEP] Exceptions
├── main.py                      # [UPDATE] New orchestration
├── config.yaml                  # [UPDATE] New config format
└── requirements.txt             # [UPDATE] Add python-telegram-bot polling
```

## Implementation Plan

### Step 1: Update Configuration (src/config/settings.py)

**New Config Structure**:

**config.yaml**:
```yaml
seeker:
  tc_url: "https://moodle.czu.cz/mod/tcb/view.php?id=776603"
  test_name: "Zápočtový test"  # Specific test section to monitor
  check_interval: 60  # seconds
  date_range:
    start: "2026-01-15"
    end: "2026-01-31"
  time_range:
    start: "10:00"
    end: "18:00"

target_tcs:
  - name: "UNIX Exam"
    url: "https://moodle.czu.cz/mod/tcb/view.php?id=XXXXXX"
  - name: "Algorithms Exam"
    url: "https://moodle.czu.cz/mod/tcb/view.php?id=YYYYYY"
```

**settings.py updates**:
```python
class SeekerConfig(BaseModel):
    tc_url: str
    test_name: str
    check_interval: int = Field(default=60, ge=30)
    date_range: DateTimeRange
    time_range: DateTimeRange

class TargetTC(BaseModel):
    name: str
    url: str

class Settings(BaseSettings):
    # ... existing fields ...
    seeker: SeekerConfig
    target_tcs: List[TargetTC] = []
```

### Step 2: Update TC Parser (src/scraper/tc_parser.py)

**New Methods Needed**:

```python
class TCPageParser:
    def get_test_sections(self, soup: BeautifulSoup) -> List[Dict]:
        """
        Parse all test sections from TC page

        Returns:
        [
            {
                'test_name': 'Zápočtový test',
                'test_url': 'https://...',
                'reserved_slots': [...],
                'available_slots': [...]
            }
        ]
        """
        pass

    def get_reserved_slots_for_test(self, soup: BeautifulSoup, test_name: str) -> List[Dict]:
        """
        Extract reserved slots for specific test section

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
        pass

    def get_available_slots_for_test(self, soup: BeautifulSoup, test_name: str) -> List[Dict]:
        """
        Extract available slots for specific test section

        NOTE: PENDING HTML structure from user

        Returns:
        [
            {
                'date': '20.01.2026',
                'time': '14:00',
                'register_url': 'https://...',
                'capacity': 1
            }
        ]
        """
        pass

    def is_registered_for_test(self, soup: BeautifulSoup, test_name: str) -> bool:
        """Check if user is registered for specific test section"""
        reserved = self.get_reserved_slots_for_test(soup, test_name)
        return len(reserved) > 0
```

### Step 3: Update Booking Module (src/booking/)

**Update auto_booker.py**:

```python
class AutoBooker:
    def unregister_slot(self, unregister_url: str) -> bool:
        """
        Unregister from a slot using unregister URL

        Example URL: https://moodle.czu.cz/mod/tcb/view.php?id=776603&unregister=407275#tc

        Steps:
        1. GET the unregister URL
        2. Verify unregistration success
        3. Return True if successful
        """
        pass

    def register_slot(self, register_url: str) -> bool:
        """
        Register for a slot using registration URL

        NOTE: PENDING HTML structure to determine URL format

        Steps:
        1. POST to registration URL (or click registration link)
        2. Handle any confirmation dialogs
        3. Verify registration success
        4. Return True if successful
        """
        pass
```

**New slot_transfer.py**:

```python
class SlotTransfer:
    """Handle slot transfer from seeker to target TC"""

    def __init__(self, session: requests.Session, parser: TCPageParser, booker: AutoBooker):
        self.session = session
        self.parser = parser
        self.booker = booker

    def transfer_slot(self, seeker_tc_url: str, seeker_test_name: str, target_tc_url: str, slot_date: str, slot_time: str) -> bool:
        """
        Transfer slot from seeker TC to target TC

        Steps:
        1. Get seeker TC page, extract unregister URL for the slot
        2. Get target TC page
        3. Check if target TC has same date/time slot available
        4. If target already registered, unregister first
        5. Register for new slot in target TC
        6. Unregister from seeker TC (free it up)
        7. Verify entire transfer succeeded
        8. Return True if successful
        """
        pass

    def find_matching_slot_in_target(self, target_soup: BeautifulSoup, date: str, time: str) -> Optional[Dict]:
        """
        Find slot with matching date/time in target TC available slots

        Returns slot dict if found, None if not available
        """
        pass
```

### Step 4: Update Telegram Module (src/notifications/)

**Update telegram_notifier.py**:

```python
class TelegramNotifier:
    # ... existing methods ...

    async def notify_slot_found_and_booked(self, test_name: str, slot: Dict, target_tcs: List[str]):
        """
        Notify that seeker found and booked a slot
        Ask user which TC to transfer to

        Message format:
        "
        Found and booked slot in Seeker TC

        Test: Zápočtový test
        Date: 20.01.2026
        Time: 14:00

        Which TC should I transfer this to?
        Reply with:
        1. UNIX Exam
        2. Algorithms Exam

        Or reply with TC URL
        "
        """
        pass

    async def notify_transfer_started(self, target_tc_name: str):
        """Notify that transfer process started"""
        pass

    async def notify_transfer_success(self, target_tc_name: str, slot: Dict):
        """Notify that transfer completed successfully"""
        pass

    async def notify_transfer_failed(self, target_tc_name: str, error: str):
        """Notify that transfer failed"""
        pass
```

**New telegram_listener.py**:

```python
from telegram.ext import Application, MessageHandler, filters
import asyncio

class TelegramListener:
    """Listen for user responses to bot messages"""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.pending_response = None  # Stores expected response type
        self.response_queue = asyncio.Queue()

    async def start_listening(self):
        """Start Telegram bot polling for messages"""
        application = Application.builder().token(self.bot_token).build()
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        await application.run_polling()

    async def handle_message(self, update, context):
        """Handle incoming Telegram message"""
        if update.message.chat_id != int(self.chat_id):
            return  # Ignore messages from other chats

        message_text = update.message.text

        if self.pending_response == "target_tc":
            await self.response_queue.put({
                'type': 'target_tc',
                'value': message_text
            })

    async def wait_for_target_tc_response(self, timeout: int = 3600) -> str:
        """
        Wait for user to reply with target TC

        Returns: TC URL or name
        Raises: TimeoutError if no response within timeout
        """
        self.pending_response = "target_tc"

        try:
            response = await asyncio.wait_for(self.response_queue.get(), timeout=timeout)
            return response['value']
        finally:
            self.pending_response = None

    def parse_target_tc(self, response: str, target_tcs: List[TargetTC]) -> str:
        """
        Parse user response to extract TC URL

        Handles:
        - Direct URL: "https://moodle.czu.cz/mod/tcb/view.php?id=XXXXXX"
        - TC name: "UNIX Exam"
        - Number: "1" (index in target_tcs list)

        Returns: TC URL
        """
        # Check if it's a URL
        if response.startswith("http"):
            return response

        # Check if it's a number (index)
        try:
            index = int(response) - 1  # 1-based index
            if 0 <= index < len(target_tcs):
                return target_tcs[index].url
        except ValueError:
            pass

        # Check if it matches a TC name
        for tc in target_tcs:
            if tc.name.lower() in response.lower():
                return tc.url

        raise ValueError(f"Could not parse target TC from response: {response}")
```

### Step 5: Update Monitor (src/scheduler/monitor.py)

**Major Rewrite**:

```python
class TCMonitor:
    """Monitor seeker TC and handle slot transfers"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.scheduler = AsyncIOScheduler()

        # ... existing auth setup ...

        self.parser = TCPageParser(self.authenticator.session)
        self.booker = AutoBooker(self.authenticator.session, self.parser)
        self.transfer = SlotTransfer(self.authenticator.session, self.parser, self.booker)
        self.detector = SlotDetector()

        self.notifier = TelegramNotifier(
            settings.telegram_bot_token,
            settings.telegram_chat_id
        )
        self.listener = TelegramListener(
            settings.telegram_bot_token,
            settings.telegram_chat_id
        )

        self.currently_holding_slot = None  # Track slot held in seeker

    def start(self):
        """Start monitoring seeker TC"""
        # Start Telegram listener in background
        asyncio.create_task(self.listener.start_listening())

        # Add seeker monitoring job
        self.scheduler.add_job(
            self.check_seeker_tc,
            trigger=IntervalTrigger(seconds=self.settings.seeker.check_interval),
            id="seeker_monitor",
            max_instances=1
        )

        self.scheduler.start()

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
            # ... authentication check ...

            soup = self.parser.fetch_tc_page(self.settings.seeker.tc_url)

            # Check if already registered (shouldn't be, but double-check)
            if self.parser.is_registered_for_test(soup, self.settings.seeker.test_name):
                logger.warning("Seeker TC already registered - this shouldn't happen")
                # TODO: Auto-unregister? Or alert user?
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

        except Exception as e:
            logger.exception(f"Error checking seeker TC: {e}")
            await self.notifier.notify_error(f"Error checking seeker: {e}")

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
            logger.warning("Transfer timeout - unregistering from seeker")
            # TODO: Should we unregister from seeker automatically?

        except Exception as e:
            await self.notifier.notify_error(f"Transfer error: {e}")
            logger.exception(f"Error during transfer: {e}")

        finally:
            self.currently_holding_slot = None
```

### Step 6: Update Main Entry Point (main.py)

```python
async def main():
    settings = Settings.load_with_config()
    logger = setup_logging(settings.log_level)
    logger.info("Starting Moodle TC Seeker & Transfer Bot")

    monitor = TCMonitor(settings)

    try:
        await monitor.notifier.notify_monitoring_started(1)  # 1 seeker TC

        monitor.start()
        logger.info(f"Monitoring seeker TC: {settings.seeker.test_name}")

        # Keep running
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
    finally:
        monitor.stop()
        logger.info("Bot stopped")
```

## Critical Implementation Requirements

### HTML Structure - CONFIRMED ✓

**Booking Workflow**:
1. **Fetch TC page** → Parse calendar for available dates
2. **Click date link** → `?id=776603&day=2026-01-20&quiz=801703#tc`
3. **Fetch time slots page** → Parse available time slots for that date
4. **Click time slot link** → `https://moodle.czu.cz/mod/tcb/view.php?id=776603&quiz=801703&slot=413832#tc`
5. **Confirmation dialog** → Handled by onclick="confirmTC()" (auto-confirmed when link followed)
6. **Verify booking** → Check for success confirmation

**Implementation Ready**: All HTML structures identified, can proceed with implementation

### Date/Time Format Conversion

**Czech Format** (in HTML):
- Date: `DD.MM.YYYY` (e.g., "15.01.2026")
- Time: `HH:MM` (e.g., "18:20")

**Config Format** (user input):
- Date: `YYYY-MM-DD` (ISO 8601)
- Time: `HH:MM`

**Conversion Needed**:
```python
def parse_czech_date(czech_date: str) -> datetime.date:
    """Convert DD.MM.YYYY to date object"""
    return datetime.strptime(czech_date, "%d.%m.%Y").date()

def parse_time(time_str: str) -> datetime.time:
    """Convert HH:MM to time object"""
    return datetime.strptime(time_str, "%H:%M").time()
```

### Unregister Deadline Handling

Unregister links have deadlines: `(do 15.01. 16:20)` = "until 15.01. 16:20"

**Important**: Cannot unregister after deadline. Bot should:
1. Check deadline before attempting unregister
2. Warn if transfer might fail due to deadline
3. Handle gracefully if deadline passed

## Testing Strategy

### Phase 1: Parser Testing
1. Unregister from seeker TC
2. Capture HTML with available slots
3. Test `get_available_slots_for_test()` parsing
4. Test `get_reserved_slots_for_test()` parsing
5. Test `is_registered_for_test()` detection

### Phase 2: Booking Testing
1. Test `register_slot()` with real slot
2. Verify registration succeeded
3. Test `unregister_slot()` with unregister URL
4. Verify unregistration succeeded

### Phase 3: Transfer Testing
1. Book slot in seeker manually
2. Test transfer to target TC (with unregister first)
3. Verify slot transferred correctly
4. Verify seeker freed up

### Phase 4: Integration Testing
1. Run bot with seeker monitoring
2. Wait for slot detection
3. Respond to Telegram prompt
4. Verify complete transfer workflow

### Phase 5: Edge Case Testing
- Seeker already registered (shouldn't happen)
- Target slot not available
- Unregister deadline passed
- Network failures during transfer
- Multiple simultaneous slot findings

## Security & Reliability

### Session Management
- Re-authenticate if session expires during transfer
- Save session after each successful operation

### Error Recovery
- If transfer fails mid-way:
  - Log exact failure point
  - Manual intervention might be needed
  - Don't clear `currently_holding_slot` until resolved

### Rate Limiting
- Keep check_interval >= 30 seconds
- Add jitter to avoid detection
- Respect Moodle rate limits

## Deployment

Same options as original plan (local, systemd, Docker, VPS).

**Additional Consideration**: Bot must run continuously to listen for Telegram responses, not just scheduled checks.

## Critical Files for Implementation

1. **src/scraper/tc_parser.py** - Parse test sections, available/reserved slots
2. **src/booking/auto_booker.py** - Register and unregister slots
3. **src/booking/slot_transfer.py** - Transfer logic
4. **src/notifications/telegram_listener.py** - Listen for user responses
5. **src/scheduler/monitor.py** - Seeker monitoring and transfer orchestration

## Next Steps

1. **User Action Required**: Unregister from Zápočtový test and provide HTML with available slots
2. **Implement parser methods** for available slots
3. **Implement registration logic** (depends on HTML structure)
4. **Implement Telegram listener**
5. **Implement transfer logic**
6. **Test complete workflow**
