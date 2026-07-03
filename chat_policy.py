"""Pure policies for bounded chat context and deterministic replies."""

from collections.abc import Iterable
import re


DEFAULT_MAX_CONTEXT_CHARS = 60_000


def positive_int_setting(value: str | None, default: int) -> int:
    """Parse a positive integer setting or return its safe default."""
    try:
        parsed = int(value or "")
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def bounded_context_chunks(chunks: Iterable[dict], max_chars: int = DEFAULT_MAX_CONTEXT_CHARS) -> list[dict]:
    """Keep ordered chunks within a total character budget without splitting them."""
    if max_chars < 1:
        return []
    selected = []
    used = 0
    for chunk in chunks:
        text = str(chunk.get("text", "")).strip()
        if not text:
            continue
        if used + len(text) > max_chars:
            break
        selected.append(chunk)
        used += len(text)
    return selected


def detect_question_language(question: str) -> str:
    """Detect common supported languages using conservative textual markers."""
    words = re.sub(r"[^\w¿¡]+", " ", question.casefold(), flags=re.UNICODE)
    normalized = f" {words} "
    markers = {
        "es": ("¿", "¡", " qué ", " cómo ", " cuál ", " dónde ", " quién ", " necesito ", " tengo ", " hola "),
        "nl": (" wat ", " hoe ", " waar ", " waarom ", " welke ", " kunt ", " heb ", " hallo "),
        "de": (" was ", " wie ", " wie viel ", " warum ", " welche ", " können ", " brauche ", " hallo "),
        "fr": (" qu'est", " quoi ", " comment ", " où ", " pourquoi ", " quel", " pouvez ", " bonjour "),
        "it": (" cosa ", " che ", " come ", " dove ", " perché ", " quale ", " puoi ", " bisogno ", " ciao "),
        "pt": (" o que ", " como ", " onde ", " por que ", " qual ", " você ", " preciso ", " olá "),
    }
    scores = {language: sum(marker in normalized for marker in values) for language, values in markers.items()}
    language, score = max(scores.items(), key=lambda item: item[1])
    return language if score else "en"


def no_info_reply(question: str) -> str:
    """Return Emma's deterministic no-context reply in the detected language."""
    messages = {
        "es": "No tengo información en los documentos disponibles para responder eso.",
        "nl": "Ik heb geen informatie in de beschikbare documenten om dat te beantwoorden.",
        "de": "In den verfügbaren Dokumenten habe ich keine Informationen, um das zu beantworten.",
        "fr": "Je ne dispose d'aucune information dans les documents disponibles pour répondre à cela.",
        "it": "Non ho informazioni nei documenti disponibili per rispondere.",
        "pt": "Não tenho informações nos documentos disponíveis para responder a isso.",
        "en": "I do not have information in the available documents to answer that.",
    }
    return f"[NO INFO]\n{messages[detect_question_language(question)]}"
