import uuid

from app.observability.logging import (
    request_id_context,
)

MAX_REQUEST_ID_LENGTH = 128


def new_request_id() -> str:
    return str(uuid.uuid4())


def parse_request_id(value: bytes | None) -> str:
    if value is None:
        return new_request_id()

    try:
        request_id = value.decode("ascii")
    except UnicodeDecodeError:
        return new_request_id()

    if (
        request_id
        and len(request_id) <= MAX_REQUEST_ID_LENGTH
        and all(char.isalnum() or char in "-_." for char in request_id)
    ):
        return request_id

    return new_request_id()


class RequestIdMiddleware:

    def __init__(
        self,
        app,
    ):
        self.app = app

    async def __call__(
        self,
        scope,
        receive,
        send,
    ):
        if scope["type"] != "http":
            await self.app(
                scope,
                receive,
                send,
            )
            return

        headers = dict(
            scope.get(
                "headers",
                [],
            )
        )

        request_id = parse_request_id(headers.get(b"x-request-id"))

        token = request_id_context.set(request_id)

        async def send_with_request_id(
            message,
        ):
            if message["type"] == "http.response.start":
                headers = list(
                    message.get(
                        "headers",
                        [],
                    )
                )

                headers.append(
                    (
                        b"x-request-id",
                        request_id.encode("utf-8"),
                    )
                )

                message["headers"] = headers

            await send(message)

        try:
            await self.app(
                scope,
                receive,
                send_with_request_id,
            )

        finally:
            request_id_context.reset(token)
