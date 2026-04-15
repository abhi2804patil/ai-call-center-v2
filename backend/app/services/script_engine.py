import logging

logger = logging.getLogger(__name__)

VALID_VOICES = {"meera", "arvind"}
VALID_NEXT_ACTIONS = {"listen", "end", "transfer"}
REQUIRED_NODES = {"greeting", "closing", "fallback"}


class ScriptEngine:
    @staticmethod
    def validate_script(content: dict) -> list[str]:
        errors = []

        nodes = content.get("nodes", {})
        if not nodes:
            errors.append("Script must have at least one node")
            return errors

        for required in REQUIRED_NODES:
            if required not in nodes:
                errors.append(f"Required node '{required}' is missing")

        supported_languages = content.get("supported_languages", [])
        if not supported_languages:
            errors.append("Must have at least one supported language")

        voice_id = content.get("voice_id", "")
        if voice_id and voice_id not in VALID_VOICES:
            errors.append(f"Invalid voice_id '{voice_id}'. Must be one of: {VALID_VOICES}")

        for node_key, node_config in nodes.items():
            text_map = node_config.get("text", {})
            if not text_map:
                errors.append(f"Node '{node_key}' must have at least one language text")
                continue

            for lang in text_map:
                if lang not in supported_languages:
                    errors.append(
                        f"Node '{node_key}' has text for language '{lang}' "
                        f"which is not in supported_languages"
                    )

            next_action = node_config.get("next_action", "listen")
            if next_action not in VALID_NEXT_ACTIONS:
                errors.append(
                    f"Node '{node_key}' has invalid next_action '{next_action}'. "
                    f"Must be one of: {VALID_NEXT_ACTIONS}"
                )

        intent_map = content.get("intent_map", {})
        if len(intent_map) < 2:
            errors.append("intent_map must have at least 2 intents")

        return errors

    @staticmethod
    def get_node(content: dict, node_key: str) -> dict | None:
        return content.get("nodes", {}).get(node_key)

    @staticmethod
    def get_all_intents(content: dict) -> list[str]:
        intents = list(content.get("intent_map", {}).keys())
        if "fallback" not in intents:
            intents.append("fallback")
        if "transfer" not in intents:
            intents.append("transfer")
        return intents

    @staticmethod
    def get_audio_text_for_node(content: dict, node_key: str, language_code: str) -> str | None:
        node = content.get("nodes", {}).get(node_key)
        if not node:
            return None
        return node.get("text", {}).get(language_code)

    @staticmethod
    def get_next_node_for_intent(content: dict, current_node: str, intent: str) -> str:
        nodes = content.get("nodes", {})
        if intent in nodes:
            return intent
        if intent == "transfer" and "transfer" in nodes:
            return "transfer"
        return "fallback"

    @staticmethod
    def count_audio_files_needed(content: dict) -> int:
        nodes = content.get("nodes", {})
        languages = content.get("supported_languages", [])
        count = 0
        for node_key, node_config in nodes.items():
            text_map = node_config.get("text", {})
            for lang in languages:
                if lang in text_map and text_map[lang]:
                    count += 1
        return count
