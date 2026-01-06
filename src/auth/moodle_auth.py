import requests
from bs4 import BeautifulSoup
from loguru import logger
from src.utils.exceptions import AuthenticationError


class MoodleAuthenticator:
    """Handles Moodle UIS authentication"""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.login_url = f"{base_url}/login/index.php"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

    def login(self, username: str, password: str) -> bool:
        """
        Authenticate with Moodle UIS credentials

        Steps:
        1. GET login page to extract logintoken from HTML
        2. POST credentials with logintoken
        3. Verify authentication via session cookie
        4. Return authenticated session
        """
        try:
            logger.info("Attempting to authenticate with Moodle")

            response = self.session.get(self.login_url)
            response.raise_for_status()

            logintoken = self._extract_login_token(response.text)
            if not logintoken:
                raise AuthenticationError("Failed to extract logintoken from login page")

            login_data = {
                'username': username,
                'password': password,
                'logintoken': logintoken
            }

            response = self.session.post(self.login_url, data=login_data, allow_redirects=True)
            response.raise_for_status()

            if self.is_authenticated():
                logger.success("Successfully authenticated with Moodle")
                return True
            else:
                raise AuthenticationError("Login failed - invalid credentials or authentication check failed")

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during authentication: {e}")
            raise AuthenticationError(f"Network error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during authentication: {e}")
            raise AuthenticationError(f"Authentication failed: {e}")

    def is_authenticated(self) -> bool:
        """Check if current session is authenticated"""
        try:
            response = self.session.get(f"{self.base_url}/my/")

            if response.status_code == 200 and 'login/index.php' not in response.url:
                return True
            return False
        except Exception as e:
            logger.warning(f"Error checking authentication status: {e}")
            return False

    def _extract_login_token(self, html: str) -> str:
        """Parse HTML to find hidden logintoken field"""
        try:
            soup = BeautifulSoup(html, 'lxml')
            logintoken_input = soup.find('input', {'name': 'logintoken'})

            if logintoken_input and logintoken_input.get('value'):
                return logintoken_input['value']

            logger.warning("Could not find logintoken in HTML")
            return None
        except Exception as e:
            logger.error(f"Error parsing login token: {e}")
            return None
