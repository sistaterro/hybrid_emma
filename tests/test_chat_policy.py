import unittest

from chat_policy import bounded_context_chunks, detect_question_language, no_info_reply, positive_int_setting


class ChatPolicyTests(unittest.TestCase):
    """Unit tests for context and deterministic response policies."""

    def test_context_budget_keeps_order_and_whole_chunks(self):
        """The context budget should stop before the first oversized remainder."""
        chunks = [
            {"source": "a", "text": "a" * 10},
            {"source": "b", "text": "b" * 10},
            {"source": "c", "text": "c" * 10},
        ]

        selected = bounded_context_chunks(chunks, max_chars=21)

        self.assertEqual([chunk["source"] for chunk in selected], ["a", "b"])

    def test_no_info_reply_supports_common_languages(self):
        """Deterministic replies should follow common user languages."""
        examples = {
            "¿Qué dice el documento?": "es",
            "Wat staat er in het document?": "nl",
            "Was steht im Dokument?": "de",
            "Bonjour, que dit le document ?": "fr",
            "Cosa dice il documento?": "it",
            "O que diz o documento?": "pt",
            "What does the document say?": "en",
        }
        for question, language in examples.items():
            with self.subTest(language=language):
                self.assertEqual(detect_question_language(question), language)
                self.assertTrue(no_info_reply(question).startswith("[NO INFO]\n"))

    def test_invalid_context_setting_uses_default(self):
        """Invalid or non-positive budgets should not prevent startup."""
        self.assertEqual(positive_int_setting("invalid", 100), 100)
        self.assertEqual(positive_int_setting("0", 100), 100)
        self.assertEqual(positive_int_setting("250", 100), 250)


if __name__ == "__main__":
    unittest.main()
