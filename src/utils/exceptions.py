class TCBotException(Exception):
    """Base exception for TC bot"""
    pass


class AuthenticationError(TCBotException):
    """Failed to authenticate with Moodle"""
    pass


class SessionExpiredError(TCBotException):
    """Moodle session expired"""
    pass


class ParsingError(TCBotException):
    """Failed to parse TC page"""
    pass


class BookingError(TCBotException):
    """Failed to book slot"""
    pass


class NotificationError(TCBotException):
    """Failed to send notification"""
    pass
