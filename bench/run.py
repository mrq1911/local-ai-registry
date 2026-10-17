#!/usr/bin/env python3

import argparse
import contextlib
import csv
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import socket
import statistics
import sys
import tempfile
from datetime import datetime, timezone
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
PRESETS = {
    "reasoning": {
        "task": "inspect_evals.mmlu_pro:mmlu_pro",
        "args": {"shuffle": False, "fewshot": 0},
    },
    "instructions": {"task": "inspect_evals.ifeval:ifeval", "args": {}},
    "tools": {
        "task": "inspect_evals.bfcl:bfcl",
        "args": {"categories": ["simple_python", "multiple", "parallel", "parallel_multiple", "irrelevance"]},
    },
    "coding": {"task": "inspect_evals.bigcodebench:bigcodebench", "args": {"version": "v0.1.2"}},
    "agent-coding": {
        "task": "inspect_harbor:aider_polyglot",
        "args": {
            "ref": "sha256:01e28d85e46beae5b7e29a29f57cb49d882b5486583d52cec4ee5bf3540a1c84",
            "dataset_task_names": "*polyglot_python_*",
        },
    },
}
QUICK = ["reasoning", "instructions", "tools"]


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def base_url(value):
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise argparse.ArgumentTypeError("supply an http(s) API base URL, including /v1 if required")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise argparse.ArgumentTypeError("credentials, query strings and fragments are not allowed; use --api-key-file")
    return value.rstrip("/")


def json_object(value):
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise argparse.ArgumentTypeError("supply a JSON object") from error
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("supply a JSON object")
    return parsed


def parser():
    cli = argparse.ArgumentParser(description="local model evaluations with Inspect AI")
    commands = cli.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="list available presets")
    run = commands.add_parser("run", help="evaluate a model served by your API endpoint")
    run.add_argument("preset", choices=["quick", *PRESETS])
    run.add_argument("--base-url", required=True, type=base_url)
    run.add_argument("--model", required=True, help="model ID accepted by the server")
    run.add_argument("--label", required=True, help="comparison label, e.g. model-a-q4")
    run.add_argument("--machine", default="", help="your label for the serving computer")
    run.add_argument("--details", default="", help="weights, quantization, engine, context and thinking settings")
    run.add_argument("--api-key-file", type=lambda value: Path(value).expanduser().resolve())
    run.add_argument("--limit", type=positive, help="samples per preset (default: 20, or 5 for agent tasks)")
    run.add_argument("--epochs", type=positive, default=1)
    run.add_argument("--seed", type=int, default=42, help="dataset shuffle seed")
    run.add_argument("--max-tokens", type=positive, default=8192, help="maximum output tokens per model call")
    run.add_argument("--temperature", type=float, default=0)
    run.add_argument("--agent-turns", type=positive, default=30)
    run.add_argument("--agent-output-tokens", type=positive, default=32768)
    run.add_argument("--time-limit", type=positive, default=900, help="seconds per sample")
    run.add_argument("--request-timeout", type=positive, default=600, help="seconds per API request")
    run.add_argument("--chat-template-kwargs", type=json_object,
                     help="server-supported chat template options as a JSON object")
    run.add_argument("--dry-run", action="store_true", help="print settings without loading tasks or contacting servers")
    report = commands.add_parser("summary", help="compare locally saved scores and timings")
    report.add_argument("--csv", action="store_true")
    report.add_argument("--log-dir", type=lambda value: Path(value).expanduser().resolve(), default=RESULTS)
    view = commands.add_parser("view", help="open the local Inspect results viewer")
    view.add_argument("--port", type=positive, default=7575)
    return cli


def settings(args, preset):
    agent = preset.startswith("agent-")
    return {
        "preset": preset,
        "task": PRESETS[preset]["task"],
        "task_args": PRESETS[preset]["args"],
        "limit": args.limit or (5 if agent else 20),
        "epochs": args.epochs,
        "sample_shuffle": args.seed,
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
        "turn_limit": args.agent_turns if agent else None,
        "token_limit": f"output:{args.agent_output_tokens}" if agent else None,
        "time_limit": args.time_limit,
        "timeout": args.request_timeout,
        "max_retries": 1,
        "max_samples": 1,
        "max_connections": 1,
        "sandbox_network": "none",
        "model_args": {"strict_tools": False, "stream": False},
        "extra_body": ({"chat_template_kwargs": args.chat_template_kwargs}
                       if args.chat_template_kwargs is not None else None),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "requirements_sha256": hashlib.sha256((ROOT / "requirements.txt").read_bytes()).hexdigest(),
    }


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:12]


def configure_environment():
    for key in list(os.environ):
        if key.startswith(("INSPECT_", "OTEL_", "LOGFIRE_", "WANDB_")):
            del os.environ[key]
    cache = ROOT / ".cache"
    paths = {
        "XDG_CACHE_HOME": cache,
        "XDG_DATA_HOME": cache / "data",
        "XDG_CONFIG_HOME": cache / "config",
        "HF_HOME": cache / "huggingface",
        "HF_DATASETS_CACHE": cache / "huggingface" / "datasets",
        "INSPECT_EVALS_CACHE_DIR": cache / "evals",
        "INSPECT_HARBOR_CACHE_DIR": cache / "harbor",
        "TMPDIR": cache / "tmp",
    }
    for key, path in paths.items():
        path.mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(path)
    os.environ.update(DO_NOT_TRACK="1", HF_HUB_DISABLE_TELEMETRY="1",
                      HF_HUB_DISABLE_IMPLICIT_TOKEN="1", INSPECT_HARBOR_NO_TELEMETRY="1")


@contextlib.contextmanager
def working_directory():
    previous = Path.cwd()
    with tempfile.TemporaryDirectory(dir=ROOT / ".cache" / "tmp", prefix="run-") as directory:
        # stop automatic dotenv discovery before it reaches user files.
        (Path(directory) / ".env").write_text("")
        os.chdir(directory)
        try:
            yield
        finally:
            os.chdir(previous)


def load_task(config):
    module, name = config["task"].split(":")
    task = getattr(importlib.import_module(module), name)(**config["task_args"])
    if config["preset"].startswith("agent-"):
        from inspect_ai.util import ComposeConfig

        for sample in task.dataset:
            compose = sample.sandbox.config
            if not isinstance(compose, ComposeConfig):
                raise ValueError("expected a Docker compose configuration for the agent sandbox")
            for service in compose.services.values():
                service.networks = None
                service.network_mode = "none"
                service.ports = None
                if service.build is not None:
                    prepare_agent_image(service)
            compose.networks = None
    return task


def prepare_agent_image(service):
    context = Path(service.build.context)
    original = context / (service.build.dockerfile or "Dockerfile")
    content = original.read_text() + "\nRUN pip3 install --no-cache-dir pytest==8.3.5\nENV PIP_NO_INDEX=1\n"
    digest = hashlib.sha256((str(context) + content).encode()).hexdigest()
    dockerfile = ROOT / ".cache" / "dockerfiles" / digest
    dockerfile.parent.mkdir(parents=True, exist_ok=True)
    dockerfile.write_text(content)
    service.build.dockerfile = str(dockerfile)
    service.image = f"local-eval-aider:{digest}"


def run_evaluations(args):
    from inspect_ai import eval as inspect_eval

    key = args.api_key_file.read_text().strip() if args.api_key_file else "local-no-key"
    if not key:
        raise ValueError("the API key file is empty")
    os.environ["LOCAL_API_KEY"] = key
    versions = dict(sorted((d.metadata["Name"], d.version) for d in importlib.metadata.distributions()))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    label = re.sub(r"[^a-zA-Z0-9_.-]+", "-", args.label).strip(".-") or "model"
    run_dir = RESULTS / f"{stamp}-{label}"
    run_dir.mkdir(parents=True)
    presets = QUICK if args.preset == "quick" else [args.preset]
    configs = [settings(args, preset) for preset in presets]
    manifest = {
        "label": args.label, "model": args.model, "base_url": args.base_url,
        "machine": args.machine, "details": args.details, "settings": configs, "packages": versions,
    }
    (run_dir / "run.json").write_text(json.dumps(manifest, indent=2) + "\n")
    failed = False
    for config in configs:
        task = load_task(config)
        conditions = fingerprint({"settings": config, "packages": versions})
        options = {key: config[key] for key in (
            "limit", "epochs", "sample_shuffle", "max_tokens", "temperature", "turn_limit",
            "token_limit", "time_limit", "timeout", "max_retries", "max_samples", "max_connections",
            "extra_body",
        )}
        logs = inspect_eval(
            task, model=f"openai-api/local/{args.model}", model_base_url=args.base_url,
            model_args=config["model_args"], log_dir=str(run_dir),
            metadata={"bench_label": args.label, "bench_preset": config["preset"],
                      "bench_conditions": conditions, "bench_machine": args.machine,
                      "bench_details": args.details, "sandbox_network": "none"},
            fail_on_error=False, retry_on_error=0, log_model_api=False,
            notification=False, ctl_server=False, sandbox_cleanup=True, display="plain", **options,
        )
        failed |= any(log.status != "success" or not log.results or
                      log.results.completed_samples != log.results.total_samples for log in logs)
    print(f"results: {run_dir}")
    return int(failed)


def log_rows(directory):
    from inspect_ai.log import read_eval_log

    for path in sorted(directory.rglob("*.eval")):
        log = read_eval_log(str(path))
        metadata = log.eval.metadata or {}
        samples = log.samples or []
        calls = [event.output for sample in samples for event in sample.events
                 if event.event == "model" and not event.error and event.cache != "read"]
        durations = [call.time for call in calls if call.time is not None and call.time > 0]
        measured = [call for call in calls if call.time and call.time > 0 and call.usage is not None]
        seconds = sum(call.time for call in measured)
        throughput = (sum(call.usage.output_tokens for call in measured) / seconds
                      if seconds and len(measured) == len(calls) else None)
        scores = log.results.scores if log.results else []
        metrics = [(f"{score.name}/{metric}", value.value, score.scored_samples)
                   for score in scores for metric, value in score.metrics.items()]
        if not metrics:
            metrics = [("", None, 0)]
        for metric, value, scored in metrics:
            yield {
                "label": metadata.get("bench_label", log.eval.model),
                "machine": metadata.get("bench_machine", ""),
                "preset": metadata.get("bench_preset", log.eval.task),
                "conditions": metadata.get("bench_conditions", ""),
                "status": log.status,
                "completed": log.results.completed_samples if log.results else 0,
                "planned": log.results.total_samples if log.results else log.eval.dataset.samples,
                "errors": sum(sample.error is not None for sample in samples),
                "scored": scored,
                "metric": metric,
                "value": value,
                "median_call_s": statistics.median(durations) if durations else None,
                "output_tok_per_call_s": throughput,
                "log": str(path),
            }


def summary(args):
    rows = list(log_rows(args.log_dir))
    if not rows:
        print("no evaluation logs found")
        return 0
    if args.csv:
        writer = csv.DictWriter(sys.stdout, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    else:
        for row in rows:
            value = f"{row['value']:.4f}" if row["value"] is not None else "—"
            latency = f"{row['median_call_s']:.2f}s" if row["median_call_s"] is not None else "—"
            rate = f"{row['output_tok_per_call_s']:.2f}" if row["output_tok_per_call_s"] is not None else "—"
            print(f"{row['label']} @ {row['machine'] or '?'} | {row['preset']} | {row['conditions']} | "
                  f"{row['status']} {row['completed']}/{row['planned']} errors={row['errors']} | "
                  f"{row['metric']}={value} | median call={latency} output tok/call-s={rate}")
    return 0


def main():
    cli = parser()
    args = cli.parse_args()
    if args.command == "list":
        for name, preset in PRESETS.items():
            print(f"{name:16} {preset['task']}")
        print("quick            reasoning + instructions + tools")
        return 0
    if args.command == "run":
        if not math.isfinite(args.temperature) or not 0 <= args.temperature <= 2:
            cli.error("temperature must be between 0 and 2")
        if args.dry_run:
            presets = QUICK if args.preset == "quick" else [args.preset]
            print(json.dumps([settings(args, preset) for preset in presets], indent=2))
            return 0
    python = ROOT / ".venv" / "bin" / "python"
    if not python.exists():
        cli.error("run bash bench/setup.sh first")
    if Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
        os.execv(str(python), [str(python), str(Path(__file__).resolve()), *sys.argv[1:]])
    configure_environment()
    with working_directory():
        if args.command == "run":
            return run_evaluations(args)
        if args.command == "summary":
            return summary(args)
        from inspect_ai import view

        with socket.socket() as probe:
            probe.bind(("127.0.0.1", args.port))
        RESULTS.mkdir(exist_ok=True)
        view(log_dir=str(RESULTS), recursive=True, host="127.0.0.1", port=args.port, trust_content=False)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        sys.exit(str(error))
