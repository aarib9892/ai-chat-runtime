from collections.abc import Callable

from app.tools.calculator import calculate
from app.tools.text_tools import get_text_length

TOOL_HANDLERS: dict[str, Callable] = {
    "calculate": calculate,
    "get_text_length": get_text_length,
}
