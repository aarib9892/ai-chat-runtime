import argparse
import asyncio
import json

import httpx


async def run_api_smoke(
    base_url: str,
) -> bool:

    async with httpx.AsyncClient(
        base_url=base_url,
        timeout=60.0,
    ) as client:

        # ---------------------------------
        # 1. Backend readiness through Nginx
        # ---------------------------------

        response = await client.get("/health/backend")

        if response.status_code != 200:
            print(
                "FAIL health check:",
                response.status_code,
            )
            return False

        print("PASS health check")

        # ---------------------------------
        # 2. Create conversation
        # ---------------------------------

        response = await client.post(
            "/api/conversations",
            json={
                "title": None,
            },
        )

        if response.status_code != 200:
            print(
                "FAIL conversation creation:",
                response.status_code,
                response.text,
            )
            return False

        conversation = response.json()

        conversation_id = conversation["id"]

        print(
            "PASS conversation creation:",
            conversation_id,
        )

        # ---------------------------------
        # 3. Stream assistant response
        # ---------------------------------

        saw_delta = False
        saw_done = False
        saw_error = False

        response_text = ""

        async with client.stream(
            "POST",
            (f"/api/conversations/" f"{conversation_id}/ask"),
            json={
                "message": (
                    "Reply with one short sentence " "containing the text smoke-ok."
                )
            },
        ) as response:

            if response.status_code != 200:
                body = await response.aread()

                print(
                    "FAIL ask endpoint:",
                    response.status_code,
                    body.decode(),
                )

                return False

            request_id = response.headers.get("x-request-id")

            if request_id:
                print(
                    "PASS request id:",
                    request_id,
                )
            else:
                print("FAIL missing request id")
                return False

            async for line in response.aiter_lines():
                if not line.strip():
                    continue

                event = json.loads(line)

                event_type = event.get("type")

                if event_type == "delta":
                    saw_delta = True

                    response_text += event.get(
                        "delta",
                        "",
                    )

                elif event_type == "done":
                    saw_done = True

                elif event_type == "error":
                    saw_error = True

                    print(
                        "FAIL stream error:",
                        event,
                    )

        if saw_error:
            return False

        if not saw_delta:
            print("FAIL no delta events")
            return False

        if not saw_done:
            print("FAIL no done event")
            return False

        print("PASS streaming")

        if "smoke-ok" not in response_text.lower():
            print(
                "FAIL unexpected response:",
                response_text,
            )
            return False

        print("PASS assistant response")

        # ---------------------------------
        # 4. Reload persisted conversation
        # ---------------------------------

        response = await client.get((f"/api/conversations/" f"{conversation_id}"))

        if response.status_code != 200:
            print(
                "FAIL conversation reload:",
                response.status_code,
            )
            return False

        conversation = response.json()

        messages = conversation.get("messages", [])

        assistant_messages = [
            message for message in messages if (message.get("role") == "assistant")
        ]

        if not assistant_messages:
            print("FAIL assistant message " "not persisted")
            return False

        last_assistant = assistant_messages[-1]

        if last_assistant.get("status") != "completed":
            print(
                "FAIL persisted status:",
                last_assistant.get("status"),
            )
            return False

        if (
            "smoke-ok"
            not in last_assistant.get(
                "content",
                "",
            ).lower()
        ):
            print("FAIL persisted content")
            return False

        print("PASS persistence reload")

        print("\nAPI SMOKE: PASS")

        return True


async def main(
    base_url: str,
) -> None:

    passed = await run_api_smoke(base_url)

    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=("Run the production HTTP " "smoke test.")
    )

    parser.add_argument(
        "--base-url",
        default="http://localhost:3000",
    )

    arguments = parser.parse_args()

    asyncio.run(main(arguments.base_url))
