import tiktoken

encoding = tiktoken.get_encoding("o200k_base")


def count_text_tokens(text: str) -> int:
    return len(encoding.encode(text))


def count_message_tokens(message: dict) -> int:
    role = message["role"]
    content = message["content"]
    role_tokens = count_text_tokens(role)
    content_tokens = count_text_tokens(content)
    return role_tokens + content_tokens


def count_context_tokens(messages: list[dict]) -> int:
    return sum(count_message_tokens(message) for message in messages)


# Return the token IDs for a text string.
def encode_text(text: str) -> list[int]:
    return encoding.encode(text)


def decode_tokens(tokens: list[int]) -> str:
    return encoding.decode(tokens)
