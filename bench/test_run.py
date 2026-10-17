import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import types
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import run


class RunnerTest(unittest.TestCase):
    def test_dry_run_needs_no_credentials_or_dependencies(self):
        args = ["run.py", "run", "quick", "--base-url", "http://localhost:8080/v1",
                "--model", "test", "--label", "test", "--api-key-file", "/missing/key", "--dry-run"]
        output = io.StringIO()
        with patch.object(run.sys, "argv", args), contextlib.redirect_stdout(output):
            self.assertEqual(run.main(), 0)
        configs = json.loads(output.getvalue())
        self.assertEqual([config["preset"] for config in configs], run.QUICK)
        self.assertEqual(configs[0]["task_args"], {"shuffle": False, "fewshot": 0})

    def test_credentials_cannot_be_embedded_in_url(self):
        for url in ("https://user:secret@localhost/v1", "http://localhost/v1?token=secret"):
            with self.assertRaises(run.argparse.ArgumentTypeError):
                run.base_url(url)

    def test_template_options_require_an_object(self):
        for value in ("[]", "null", "invalid"):
            with self.assertRaises(run.argparse.ArgumentTypeError):
                run.json_object(value)

    def test_agent_containers_have_no_network(self):
        from inspect_ai import Task
        from inspect_ai.dataset import Sample
        from inspect_ai.util import ComposeConfig, ComposeService, SandboxEnvironmentSpec

        compose = ComposeConfig(services={
            "default": ComposeService(image="fixture", network_mode="host"),
            "sidecar": ComposeService(image="fixture", networks=["external"]),
        })
        task = Task(dataset=[Sample(input="fixture", sandbox=SandboxEnvironmentSpec("docker", compose))])
        module = types.SimpleNamespace(aider_polyglot=lambda **kwargs: task)
        config = {"preset": "agent-coding", "task": "inspect_harbor:aider_polyglot", "task_args": {}}
        with patch.object(run.importlib, "import_module", return_value=module):
            loaded = run.load_task(config)
        for service in loaded.dataset[0].sandbox.config.services.values():
            self.assertEqual(service.network_mode, "none")
            self.assertIsNone(service.networks)

    def test_real_runner_and_report_against_local_fixture(self):
        from inspect_ai import Task
        from inspect_ai.dataset import Sample
        from inspect_ai.scorer import match
        from inspect_ai.solver import generate, use_tools
        from inspect_ai.tool import tool

        @tool
        def add():
            async def execute(a: int, b: int) -> str:
                """add two numbers.

                Args:
                    a: first number.
                    b: second number.
                """
                return str(a + b)
            return execute

        requests = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append((self.path, request, self.headers.get("Authorization")))
                last = request["messages"][-1]
                content = "correct" if last["content"] in ("alpha", "5") else "wrong"
                message = {"role": "assistant", "content": content}
                finish_reason = "stop"
                if last["content"] == "add":
                    message = {"role": "assistant", "content": None, "tool_calls": [
                        {"id": "call_1", "type": "function",
                         "function": {"name": "add", "arguments": '{"a": 2, "b": 3}'}}]}
                    finish_reason = "tool_calls"
                response = {
                    "id": "fixture", "object": "chat.completion", "created": 1, "model": "fixture",
                    "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
                }
                data = json.dumps(response).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory(dir=run.ROOT / ".cache" / "tmp") as directory:
                root = Path(directory)
                (root / "requirements.txt").write_text((run.ROOT / "requirements.txt").read_text())
                key = root / "key"
                key.write_text("fixture-secret")
                args = run.parser().parse_args([
                    "run", "reasoning", "--base-url", f"http://127.0.0.1:{server.server_port}/v1",
                    "--model", "fixture", "--label", "test-model", "--machine", "test-machine",
                    "--api-key-file", str(key), "--limit", "3",
                    "--chat-template-kwargs", '{"reasoning_effort":"xhigh","reasoning_strength":"xhigh","enable_thinking":true}',
                    "--max-tokens", "32768", "--request-timeout", "900",
                ])
                task = Task(dataset=[Sample(id="a", input="alpha", target="correct"),
                                     Sample(id="b", input="beta", target="correct"),
                                     Sample(id="c", input="add", target="correct")],
                            solver=[use_tools(add()), generate()], scorer=match())
                with patch.object(run, "ROOT", root), patch.object(run, "RESULTS", root / "results"), \
                        patch.dict(os.environ), patch.object(run, "load_task", return_value=task):
                    os.environ["INSPECT_TELEMETRY"] = "must.not.be.loaded"
                    run.configure_environment()
                    self.assertNotIn("INSPECT_TELEMETRY", os.environ)
                    self.assertEqual(os.environ["INSPECT_HARBOR_NO_TELEMETRY"], "1")
                    with run.working_directory():
                        self.assertEqual(run.run_evaluations(args), 0)
                        rows = list(run.log_rows(root / "results"))
                accuracy = next(row for row in rows if row["metric"].endswith("/accuracy"))
                self.assertAlmostEqual(accuracy["value"], 2 / 3)
                self.assertEqual(accuracy["completed"], 3)
                self.assertEqual(accuracy["errors"], 0)
                self.assertGreater(accuracy["median_call_s"], 0)
                self.assertGreater(accuracy["output_tok_per_call_s"], 0)
                manifest = next((root / "results").rglob("run.json")).read_text()
                self.assertNotIn("fixture-secret", manifest)
                self.assertEqual(json.loads(manifest)["machine"], "test-machine")
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        self.assertEqual(len(requests), 4)
        self.assertTrue(any(request["messages"][-1]["role"] == "tool" for _, request, _ in requests))
        for path, request, auth in requests:
            self.assertEqual(path, "/v1/chat/completions")
            self.assertEqual(request["model"], "fixture")
            self.assertEqual(auth, "Bearer fixture-secret")
            self.assertEqual(request["chat_template_kwargs"], {
                "reasoning_effort": "xhigh", "reasoning_strength": "xhigh", "enable_thinking": True,
            })
            self.assertEqual(request["max_tokens"], 32768)


if __name__ == "__main__":
    unittest.main()
