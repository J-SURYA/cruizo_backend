from pathlib import Path


def load_prompt(prompt_name: str) -> str:
    """
    Load prompt from markdown file.
    """
    prompt_dir = Path(__file__).parent
    prompt_file = prompt_dir / f"{prompt_name}.md"

    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")

    with open(prompt_file, "r", encoding="utf-8") as f:
        return f.read()


def get_classify_intent_prompt(flow_context: str = "") -> str:
    """
    Get the classify intent system prompt with flow context.
    """
    prompt_template = load_prompt("classify_intent_prompt")
    return prompt_template.replace("{flow_context}", flow_context)


def get_inventory_response_prompt() -> str:
    """
    Get the inventory response system prompt.
    """
    return load_prompt("inventory_response_prompt")


def get_documents_response_prompt() -> str:
    """
    Get the documents response system prompt.
    """
    return load_prompt("documents_response_prompt")


def get_booking_response_prompt() -> str:
    """
    Get the booking response system prompt.
    """
    return load_prompt("booking_response_prompt")


def get_about_response_prompt() -> str:
    """
    Get the about response system prompt.
    """
    return load_prompt("about_response_prompt")


def get_general_response_prompt() -> str:
    """
    Get the general response system prompt.
    """
    return load_prompt("general_response_prompt")


def get_response_prompt(intent_type: str) -> str:
    """
    Get the appropriate response prompt based on intent type.
    """
    if intent_type == "inventory":
        return get_inventory_response_prompt()
    elif intent_type == "documents":
        return get_documents_response_prompt()
    elif intent_type == "booking":
        return get_booking_response_prompt()
    elif intent_type == "about":
        return get_about_response_prompt()
    elif intent_type == "general":
        return get_general_response_prompt()
    else:
        # Fallback to general response prompt
        return get_general_response_prompt()


__all__ = [
    "load_prompt",
    "get_classify_intent_prompt",
    "get_inventory_response_prompt",
    "get_documents_response_prompt",
    "get_booking_response_prompt",
    "get_about_response_prompt",
    "get_general_response_prompt",
    "get_response_prompt",
]
