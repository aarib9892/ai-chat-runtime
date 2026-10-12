from enum import StrEnum


class ErrorCode(StrEnum):
    INVALID_REQUEST = "INVALID_REQUEST"

    CONVERSATION_NOT_FOUND = "CONVERSATION_NOT_FOUND"

    PROVIDER_RATE_LIMITED = "PROVIDER_RATE_LIMITED"

    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"

    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"

    PROVIDER_ERROR = "PROVIDER_ERROR"

    DATABASE_ERROR = "DATABASE_ERROR"

    AGENT_RUNTIME_ERROR = "AGENT_RUNTIME_ERROR"

    INTERNAL_ERROR = "INTERNAL_ERROR"

    CONVERSATION_BUSY = "CONVERSATION_BUSY"

    SERVER_BUSY = "SERVER_BUSY"

    RATE_LIMITED = "RATE_LIMITED"


class AppError(Exception):
    code: ErrorCode
    public_message: str
    status_code: int
    retryable: bool

    def __init__(
        self,
        *,
        code: ErrorCode,
        public_message: str,
        status_code: int,
        retryable: bool = False,
    ):
        super().__init__(public_message)

        self.code = code
        self.public_message = public_message
        self.status_code = status_code
        self.retryable = retryable


class InvalidRequestError(AppError):
    def __init__(
        self,
        message: str = "Invalid request.",
    ):
        super().__init__(
            code=ErrorCode.INVALID_REQUEST,
            public_message=message,
            status_code=400,
            retryable=False,
        )


class ConversationNotFoundError(AppError):
    def __init__(self):
        super().__init__(
            code=(ErrorCode.CONVERSATION_NOT_FOUND),
            public_message=("Conversation not found."),
            status_code=404,
            retryable=False,
        )


class ProviderRateLimitError(AppError):
    def __init__(self):
        super().__init__(
            code=(ErrorCode.PROVIDER_RATE_LIMITED),
            public_message=(
                "The AI service is " "temporarily busy. " "Please try again."
            ),
            status_code=503,
            retryable=True,
        )


class ProviderTimeoutError(AppError):
    def __init__(self):
        super().__init__(
            code=(ErrorCode.PROVIDER_TIMEOUT),
            public_message=("The AI service timed out. " "Please try again."),
            status_code=504,
            retryable=True,
        )


class ProviderUnavailableError(AppError):
    def __init__(self):
        super().__init__(
            code=(ErrorCode.PROVIDER_UNAVAILABLE),
            public_message=("The AI service is " "temporarily unavailable."),
            status_code=503,
            retryable=True,
        )


class ProviderError(AppError):
    def __init__(self):
        super().__init__(
            code=ErrorCode.PROVIDER_ERROR,
            public_message=("The AI service could not " "complete the request."),
            status_code=502,
            retryable=True,
        )


class DatabaseError(AppError):
    def __init__(self):
        super().__init__(
            code=ErrorCode.DATABASE_ERROR,
            public_message=("A database operation " "failed."),
            status_code=500,
            retryable=True,
        )


class AgentRuntimeError(AppError):
    def __init__(
        self,
        message: str = ("The agent could not " "complete the request."),
    ):
        super().__init__(
            code=(ErrorCode.AGENT_RUNTIME_ERROR),
            public_message=message,
            status_code=500,
            retryable=False,
        )


class ConversationBusyError(AppError):
    def __init__(self):
        super().__init__(
            code=ErrorCode.CONVERSATION_BUSY,
            public_message=(
                "A response is already being " "generated for this conversation."
            ),
            status_code=409,
            retryable=True,
        )


class ServerBusyError(AppError):
    def __init__(self):
        super().__init__(
            code=ErrorCode.SERVER_BUSY,
            public_message=(
                "The service is currently busy. " "Please try again shortly."
            ),
            status_code=503,
            retryable=True,
        )


class RateLimitedError(AppError):
    def __init__(self):
        super().__init__(
            code=ErrorCode.RATE_LIMITED,
            public_message=("Too many requests. " "Please try again shortly."),
            status_code=429,
            retryable=True,
        )
