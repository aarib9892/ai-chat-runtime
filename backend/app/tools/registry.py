from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel

from app.schemas.tools import CalculatorArgs, TextLengthArgs
from app.tools.calculator import calculate
from app.tools.text_tools import get_text_length


@dataclass(frozen=True)
class ToolSpec:
    handler: Callable[..., object]
    args_model: type[BaseModel]


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "calculate": ToolSpec(handler=calculate, args_model=CalculatorArgs),
    "get_text_length": ToolSpec(handler=get_text_length, args_model=TextLengthArgs),
}
