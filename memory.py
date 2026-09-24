"""memory.py — จัดการประวัติการสนทนา + persona ต่อ channel"""
from collections import defaultdict
from typing import Dict, List

from config import MAX_HISTORY_MESSAGES, DEFAULT_PERSONA
from personas import get_persona, PERSONAS


class ConversationMemory:
    """เก็บประวัติแยกต่อ key + บุคลิกแยกต่อ key"""

    def __init__(self, max_messages=MAX_HISTORY_MESSAGES):
        self.max_messages = max_messages
        self._store: Dict[str, List[Dict[str, str]]] = defaultdict(list)
        self._personas: Dict[str, str] = {}

    def set_persona(self, key: str, persona_name: str) -> bool:
        if persona_name not in PERSONAS:
            return False
        self._personas[key] = persona_name
        self.clear(key)
        return True

    def get_persona_name(self, key: str) -> str:
        return self._personas.get(key, DEFAULT_PERSONA)

    def get_system_prompt(self, key: str) -> str:
        return get_persona(self.get_persona_name(key))["system_prompt"]

    def get_history(self, key: str) -> List[Dict[str, str]]:
        history = self._store.get(key, [])
        return [{"role": "system", "content": self.get_system_prompt(key)}] + list(history)

    def add_user_message(self, key: str, content: str) -> None:
        self._store[key].append({"role": "user", "content": content})
        self._trim(key)

    def add_assistant_message(self, key: str, content: str) -> None:
        self._store[key].append({"role": "assistant", "content": content})
        self._trim(key)

    def clear(self, key: str) -> None:
        if key in self._store:
            del self._store[key]

    def clear_all(self) -> None:
        self._store.clear()
        self._personas.clear()

    def _trim(self, key: str) -> None:
        if len(self._store[key]) > self.max_messages:
            self._store[key] = self._store[key][-self.max_messages:]