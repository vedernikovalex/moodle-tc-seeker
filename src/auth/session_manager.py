import pickle
import os
import requests
from loguru import logger


class SessionManager:
    """Persist and restore session cookies"""

    @staticmethod
    def save_session(session: requests.Session, filepath: str):
        """Pickle session cookies to disk"""
        try:
            with open(filepath, 'wb') as f:
                pickle.dump(session.cookies, f)
            os.chmod(filepath, 0o600)
            logger.info(f"Session saved to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save session: {e}")

    @staticmethod
    def load_session(filepath: str) -> requests.Session:
        """Restore session from disk"""
        try:
            if not os.path.exists(filepath):
                logger.info(f"No session file found at {filepath}")
                return None

            with open(filepath, 'rb') as f:
                cookies = pickle.load(f)

            session = requests.Session()
            session.cookies.update(cookies)
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })

            logger.info(f"Session loaded from {filepath}")
            return session
        except Exception as e:
            logger.error(f"Failed to load session: {e}")
            return None
