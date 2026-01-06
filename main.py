import asyncio
from src.config.settings import Settings
from src.scheduler.monitor import TCMonitor
from src.utils.logger import setup_logging
from src.utils.exceptions import TCBotException


async def main():
    settings = Settings.load_with_config()

    logger = setup_logging(settings.log_level)
    logger.info("Starting Moodle TC Seeker & Transfer Bot")

    monitor = TCMonitor(settings)

    try:
        # Determine if using seeker mode or legacy multi-TC mode
        if settings.seeker:
            await monitor.notifier.notify_monitoring_started(1)
            monitor.start()
            logger.info(f"Monitoring seeker TC: {settings.seeker.test_name}")
        else:
            await monitor.notifier.notify_monitoring_started(len(settings.tc_pages))
            monitor.start()
            logger.info(f"Monitoring {len(settings.tc_pages)} TC page(s)")

        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except TCBotException as e:
        logger.error(f"Bot error: {e}")
        await monitor.notifier.notify_error(str(e))
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        await monitor.notifier.notify_error(f"Unexpected error: {e}")
    finally:
        monitor.stop()
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
