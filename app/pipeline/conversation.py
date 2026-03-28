from __future__ import annotations

from app.config import settings


class ConversationManager:
    """Maintains rolling conversation history for a single session."""

    def __init__(self, max_turns: int = 20) -> None:
        self.max_turns = max_turns
        
        combined_prompt = f"{settings.system_prompt}\n\n[INSTRUCTIONS]\n{settings.instruction_prompt}"
        
        self.messages: list[dict[str, str]] = [
            {"role": "system", "content": combined_prompt},
        ]

    def add_user_message(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})
        self._trim()

    def add_assistant_message(self, content: str) -> None:
        self.messages.append({"role": "assistant", "content": content})
        self._trim()

    def get_messages(self) -> list[dict[str, str]]:
        return list(self.messages)

    def _trim(self) -> None:
        """Keep the system prompt + the last max_turns pairs."""
        system = self.messages[0]
        conversation = self.messages[1:]
        max_msgs = self.max_turns * 2
        if len(conversation) > max_msgs:
            self.messages = [system] + conversation[-max_msgs:]
