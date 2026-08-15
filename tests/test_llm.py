import unittest
import urllib.error
from unittest.mock import patch

from qq_cf_bot.llm import (
    OpenAICompatibleTextClient,
    _read_responses_websocket_json,
    endpoint_url,
    extract_text,
    infer_wire_api,
    normalize_wire_api,
)


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
        self.assertEqual(
            endpoint_url("http://100.64.0.1:8080", "responses_websocket"),
            "ws://100.64.0.1:8080/responses",
        )
        self.assertEqual(
            endpoint_url("https://api.openai.com/v1", "responses_ws"),
            "wss://api.openai.com/v1/responses",
        )
        self.assertEqual(
            endpoint_url("ws://100.64.0.1:8080/responses", "chat_completions"),
            "http://100.64.0.1:8080/chat/completions",
        )

    def test_infer_wire_api_from_endpoint_url(self):
        self.assertEqual(infer_wire_api("https://api.openai.com/v1/responses"), "responses")
        self.assertEqual(infer_wire_api("ws://100.64.0.1:8080/responses"), "responses_websocket")
        self.assertEqual(
            infer_wire_api("https://api.openai.com/v1/chat/completions"),
            "chat_completions",
        )

    def test_normalizes_responses_websocket_aliases(self):
        self.assertEqual(normalize_wire_api("responses-websocket"), "responses_websocket")
        self.assertEqual(normalize_wire_api("responses_ws"), "responses_websocket")
        self.assertEqual(normalize_wire_api("websocket"), "responses_websocket")

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

    def test_collects_responses_websocket_output_text_events(self):
        websocket = FakeWebSocket(
            [
                {"type": "response.created"},
                {"type": "response.output_text.delta", "delta": "{\"accepted\":"},
                {"type": "response.output_text.delta", "delta": "true}"},
                {"type": "response.completed", "response": {"output": []}},
            ]
        )

        self.assertEqual(_read_responses_websocket_json(websocket, 60), "{\"accepted\":true}")

    def test_collects_responses_websocket_completed_response(self):
        websocket = FakeWebSocket(
            [
                {
                    "type": "response.completed",
                    "response": {
                        "output": [
                            {
                                "type": "message",
                                "content": [{"type": "output_text", "text": "{\"ok\":true}"}],
                            }
                        ]
                    },
                }
            ]
        )

        self.assertEqual(_read_responses_websocket_json(websocket, 60), "{\"ok\":true}")

    def test_responses_http_426_falls_back_to_websocket(self):
        client = OpenAICompatibleTextClient("http://llm.internal", "key", "model", "responses")
        http_error = urllib.error.HTTPError(
            "http://llm.internal/responses",
            426,
            "Upgrade Required",
            {},
            FakeErrorBody(b'{"error":{"message":"WebSocket upgrade required"}}'),
        )

        with patch("urllib.request.urlopen", side_effect=http_error), patch(
            "qq_cf_bot.llm._ResponsesWebSocketTransport.complete_json",
            return_value='{"accepted":true}',
        ) as complete_json:
            self.assertEqual(client.complete_json("system", "user"), '{"accepted":true}')

        complete_json.assert_called_once_with("system", "user")


class FakeWebSocket:
    def __init__(self, events):
        import json

        self.events = [json.dumps(event) for event in events]

    def recv_text(self):
        if not self.events:
            raise EOFError("no more events")
        return self.events.pop(0)


class FakeErrorBody:
    def __init__(self, body):
        self.body = body

    def read(self):
        return self.body

    def close(self):
        pass


if __name__ == "__main__":
    unittest.main()
