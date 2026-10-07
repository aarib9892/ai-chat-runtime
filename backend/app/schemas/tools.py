from typing import Literal

from pydantic import BaseModel, ConfigDict


class CalculatorArgs(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    operation: Literal[
        "add",
        "subtract",
        "multiply",
        "divide",
    ]

    a: int | float
    b: int | float


class TextLengthArgs(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    text: str
