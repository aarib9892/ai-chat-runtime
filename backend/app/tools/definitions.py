CALCULATOR_TOOL = {
    "type": "function",
    "name": "calculate",
    "description": (
        "Perform basic arithmetic using two numbers. "
        "Use this tool when exact arithmetic is required."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": [
                    "add",
                    "subtract",
                    "multiply",
                    "divide",
                ],
                "description": ("The arithmetic operation to perform."),
            },
            "a": {
                "type": "number",
                "description": "The first number.",
            },
            "b": {
                "type": "number",
                "description": "The second number.",
            },
        },
        "required": [
            "operation",
            "a",
            "b",
        ],
        "additionalProperties": False,
    },
    "strict": True,
}
TEXT_LENGTH_TOOL = {
    "type": "function",
    "name": "get_text_length",
    "description": (
        "Return the exact number of characters "
        "in a piece of text. "
        "Use this when the user asks for the "
        "character count or length of text."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": (
                    "The exact text whose characters " "should be counted."
                ),
            },
        },
        "required": [
            "text",
        ],
        "additionalProperties": False,
    },
    "strict": True,
}

TOOLS = [CALCULATOR_TOOL, TEXT_LENGTH_TOOL]
