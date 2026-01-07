# Moodle TC Booking Bot

Automated Python bot to monitor CZU Moodle Test Centrum (TC) pages for available booking slots and automatically reserve them.

## Features

- Monitors multiple TC pages simultaneously
- Filters slots by date and time preferences
- Auto-books matching slots immediately
- Telegram notifications for all events
- Session persistence to minimize login requests
- Graceful error handling and recovery

## Prerequisites

- Python 3.10+
- CZU UIS credentials
- Telegram account

## Setup Instructions

### 1. Clone and Install Dependencies

```bash
cd /Users/alexandervedernikov/Documents/Personal/moodle-scrape
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Create Telegram Bot

1. Open Telegram and message @BotFather
2. Send `/newbot` and follow instructions
3. Copy the bot token (format: `123456789:ABCdef...`)
4. Start a conversation with your new bot
5. Get your chat ID:
   - Message @userinfobot
   - Copy your user ID number

### 3. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with your credentials:
```env
MOODLE_USERNAME=your_uis_username
MOODLE_PASSWORD=your_uis_password
TELEGRAM_BOT_TOKEN=123456789:ABCdef...
TELEGRAM_CHAT_ID=987654321
LOG_LEVEL=INFO
```

**SECURITY:** Never commit `.env` file to git

### 4. Configure TC Pages

Edit `config.yaml` to add TC pages you want to monitor:

```yaml
tc_pages:
  - id: "776603"
    name: "UNIX Exam"
    url: "https://moodle.czu.cz/mod/tcb/view.php?id=776603"
    check_interval: 60  # seconds
    date_range:
      start: "2026-01-15"  # YYYY-MM-DD
      end: "2026-01-20"
    time_range:
      start: "10:00"       # HH:MM (24-hour)
      end: "16:00"
```

**Finding TC URLs:**
1. Log into Moodle
2. Navigate to your course's Test Centrum page
3. Copy the URL (should contain `/mod/tcb/view.php?id=XXXXXX`)

## Running the Bot

```bash
source venv/bin/activate
python main.py
```

The bot will:
1. Authenticate with Moodle
2. Send Telegram notification that monitoring started
3. Check TC pages at configured intervals
4. Book matching slots automatically
5. Send notifications for all events

**Press Ctrl+C to stop the bot**

## Testing

Before running continuously, test with a single TC page:

1. Configure only one TC in `config.yaml`
2. Set date range far in the future (no slots available)
3. Run bot and verify:
   - Authentication succeeds
   - TC page fetches successfully
   - No errors in logs
   - Telegram notifications work

## Logs

Logs are stored in `logs/tc_bot_YYYY-MM-DD.log` with:
- 30-day retention
- Daily rotation
- Automatic compression

View logs:
```bash
tail -f logs/tc_bot_$(date +%Y-%m-%d).log
```

## Troubleshooting

### Authentication Failed
- Verify UIS credentials in `.env`
- Check if Moodle is accessible
- Review logs for specific error

### TC Page Not Found (404)
- Verify TC URL in `config.yaml`
- Ensure TC page exists and is accessible

### No Slots Detected
- Check date/time ranges in `config.yaml`
- Verify `get_available_slots()` is implemented correctly
- Review `tc_page.html` structure

### Telegram Notifications Not Received
- Verify bot token and chat ID in `.env`
- Start conversation with bot first
- Check Telegram API is accessible

### Session Expired Errors
- Bot should auto-re-authenticate
- Check credentials are correct
- Review session timeout settings

## Deployment Options

### Local Machine (Background)
```bash
nohup python main.py &
```

### systemd Service (Linux)
Create `/etc/systemd/system/moodle-tc-bot.service`:
```ini
[Unit]
Description=Moodle TC Booking Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/moodle-scrape
Environment="PATH=/path/to/moodle-scrape/venv/bin"
ExecStart=/path/to/moodle-scrape/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable moodle-tc-bot
sudo systemctl start moodle-tc-bot
sudo systemctl status moodle-tc-bot
```

### Docker
Build and run:
```bash
docker build -t moodle-tc-bot .
docker run -d --name tc-bot --env-file .env -v $(pwd)/logs:/app/logs moodle-tc-bot
```

## Security Best Practices

1. Never commit `.env` file
2. Keep `.session_cache.pkl` private
3. Set file permissions: `chmod 600 .env`
4. Rotate credentials periodically
5. Review logs for suspicious activity
6. Use minimum check intervals (30+ seconds)

## Project Structure

```
moodle-scrape/
├── src/
│   ├── auth/              # Authentication logic
│   ├── scraper/           # TC page parsing
│   ├── booking/           # Auto-booking logic
│   ├── notifications/     # Telegram alerts
│   ├── scheduler/         # Monitoring orchestration
│   ├── config/            # Settings management
│   └── utils/             # Logging and exceptions
├── main.py                # Entry point
├── config.yaml            # TC configuration
├── .env                   # Credentials (DO NOT COMMIT)
└── requirements.txt       # Dependencies
```

## License

MIT

## Support

For issues or questions, contact the developer.
