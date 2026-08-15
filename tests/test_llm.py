import unittest

from qq_cf_bot.llm import OpenAICompatibleTextClient, endpoint_url, extract_text, infer_wire_api


class LLMClientTest(unittest.TestCase):
    def test_endpoint_url_accepts_endpoint_or_base_url(self):
        self.assertEqual(
            endpoint_url("https://api.openai.com/v1/chat/completions", "chat_completions"),
            "https://api.openai.com/v1/chat/completions",
        )
        self.assertEqual(
            endpoint_url("https://api.openai.com/v1", "chat_completions"),
            "https://api.openai.com/v1/chat/completions",
        )
        self.assertEqual(
            endpoint_url("http://100.64.0.1:8080", "responses"),
            "http://100.64.0.1:8080/responses",
        )
        self.assertEqual(
            endpoint_url("https://api.openai.com/v1/chat/completions", "responses"),
            "https://api.openai.com/v1/responses",
        )

    def test_infer_wire_api_from_endpoint_url(self):
        self.assertEqual(infer_wire_api("https://api.openai.com/v1/responses"), "responses")
        self.assertEqual(
            infer_wire_api("https://api.openai.com/v1/chat/completions"),
            "chat_completions",
        )

    def test_builds_responses_json_payload(self):
        client = OpenAICompatibleTextClient("http://llm.internal", "key", "model", "responses")

        payload = client._payload("system", "user")

        self.assertEqual(payload["instructions"], "system")
        self.assertEqual(payload["input"][0]["content"][0]["type"], "input_text")
        self.assertEqual(payload["text"]["format"]["type"], "json_object")

    def test_extracts_text_from_chat_and_responses_results(self):
        self.assertEqual(
            extract_text({"choices": [{"message": {"content": "{\"accepted\":true}"}}]}),
            "{\"accepted\":true}",
        )
        self.assertEqual(
            extract_text(
                {
                    "output": [
                        {
                            "type": "message",
                            "content": [{"type": "output_text", "text": "{\"accepted\":false}"}],
                        }
                    ]
                }
            ),
            "{\"accepted\":false}",
        )


if __name__ == "__main__":
    unittest.main()
