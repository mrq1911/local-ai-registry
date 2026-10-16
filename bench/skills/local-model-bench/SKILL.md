---
name: local-model-bench
description: "Run and compare local model capability benchmarks through user-supplied API endpoints using the local-ai-registry bench suite. Use for reasoning, instruction following, tool use, coding, agent skills, response timing, or reviewing saved evaluation results. Keeps evaluation data on the user's machines."
---

# local model benchmarks

use the existing Inspect-based runner in the `local-ai-registry` checkout. this
workflow evaluates already-running model servers; it does not deploy models or
publish benchmark results.

## locate the suite

use the checkout supplied by the user or `LOCAL_MODEL_BENCH_REPO` when set.
otherwise check the current workspace, then `~/git/local-ai-registry`, for
`bench/run.py` and `bench/README.md`. ask for the checkout location if neither
contains the suite; do not search unrelated directories or replace it with a new
harness. read that checkout's `bench/README.md` and run `python3 bench/run.py list`
for the current presets. run commands from the checkout root.

## keep evaluation data local

- send prompts only to the user-supplied model endpoints. keep answers, transcripts,
  scores, manifests and exports on the benchmark computer under `bench/results`.
  do not submit them to cloud judges, search services, hosted dashboards or uploads.
- public package, dataset and image downloads are setup traffic, not fully offline
  operation. if the user requires no internet access at all, verify the needed
  artifacts are cached before running and report missing dependencies.
- use `--api-key-file` when authentication is required. request a file path, never
  a pasted key. do not read unrelated dotenv files or put credentials in URLs.
- run through `bench/run.py` so its telemetry suppression, dotenv isolation and
  Docker network restrictions apply. preserve those restrictions when diagnosing
  failures. keep the viewer bound to loopback.

## choose and run

reuse endpoint and model details already supplied in the conversation. each run
needs an API base URL, the exact served model ID and a comparison label. record
machine, weight revision, quantization, engine version, context and thinking
settings in `--machine` and `--details` when known; leave unknown details unstated.
derive a label from the model when none is supplied. ask together for missing
required information; do not discover machines or scan ports. these metadata flags
record the setup and do not change server configuration.

for a results-review request, inspect existing logs without starting new inference.
for a new run, use the small defaults unless the user specifies another budget.
install the pinned environment with `bash bench/setup.sh` if missing; coding and
agent tasks also need Docker and Compose. do not upgrade dependencies as a routine
part of a comparison.

| request | preset | default size |
| --- | --- | --- |
| initial general comparison | `quick` | 20 each: reasoning, instructions, tools |
| knowledge and reasoning | `reasoning` | 20 MMLU-Pro, zero-shot |
| objectively checkable chat instructions | `instructions` | 20 IFEval |
| native function calling | `tools` | 20 BFCL, selected single-turn categories |
| code generation | `coding` | 20 BigCodeBench Python tasks |
| editing, debugging and terminal tool use | `agent-coding` | 5 Aider Polyglot Python tasks with Inspect ReAct |

`quick` does not include coding or agent tasks. include the corresponding presets
when those capabilities are requested. keep all compared models on the same preset,
sample limit, shuffle seed, epochs, temperature, concurrency and token/turn/time
budgets. run models sequentially by default to avoid benchmark-induced contention.

```bash
python3 bench/run.py run agent-coding \
  --base-url http://gpu-a.local:8080/v1 --model model-a \
  --label model-a-q4 --machine gpu-a \
  --details 'q4, engine/version, 32k context, thinking enabled' --limit 5
```

substitute the supplied values, then repeat with each model under the same settings.
use `--dry-run` for command preparation without model calls, credential reads or
downloads. native API tool calling is required for tool and agent comparisons;
do not silently enable tool emulation or change the agent to improve one score.

## compare the evidence

```bash
python3 bench/run.py summary
python3 bench/run.py summary --csv
python3 bench/run.py view
```

use the viewer when requested or when transcript inspection helps. `--port` selects
another loopback port if the default 7575 is occupied. save requested CSV exports
to new filenames under `bench/results`, preserving earlier reports and logs.

compare the `conditions` fingerprints and actual sample IDs in the `.eval` logs;
check each run's `run.json` for model details and package versions. report separate
capability scores with completed/planned counts, errors and uncertainty where
available. inspect failures before interpreting a score, and retain failed runs.
do not repeatedly rerun until a score improves or silently compare mismatched
settings. a changed budget or environment requires a clearly separate comparison.

timing is median model-call latency and reported output tokens per model-call
second, including prompt processing and transport. it is not time to first token,
pure decode speed, or a saturated serving benchmark. different computers affect
timing independently of model quality; missing token usage stays unknown.

small subsets are preliminary comparisons, not official leaderboard results or a
single intelligence rating. IFEval does not grade subjective prose quality. the
agent score measures the model with Inspect ReAct, not Aider's native agent or the
user's own agent. Terminal-Bench and repository-repair tasks are not current presets.
distinguish synthetic runner checks from actual model measurements. finish with
the useful comparison, material limitations, and local paths to its evidence.
