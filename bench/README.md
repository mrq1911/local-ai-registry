# local model comparisons

[Inspect AI](https://inspect.aisi.org.uk/) runs the evaluations and provides a local
results viewer. [Inspect Evals](https://github.com/UKGovernmentBEIS/inspect_evals)
supplies the scored tasks; [Inspect Harbor](https://meridianlabs-ai.github.io/inspect_harbor/)
supplies coding and terminal environments. the runner adds repeatable presets and
a comparison report. models can run on different computers.

| preset | evaluation | measures | default samples | Docker |
| --- | --- | --- | --- | --- |
| `reasoning` | MMLU-Pro, zero-shot | knowledge and reasoning | 20 | no |
| `instructions` | IFEval | objectively checkable chat instructions | 20 | no |
| `tools` | BFCL single-turn subset | choosing tools, arguments, parallel calls, abstention | 20 | no |
| `coding` | BigCodeBench v0.1.2, complete | Python implementations graded with tests | 20 | yes |
| `agent-coding` | Aider Polyglot Python subset, Inspect ReAct agent | editing files, terminal tools and debugging | 5 | yes |
| `quick` | reasoning + instructions + tools | a first comparison | 20 each | no |

these measure different capabilities, not a single intelligence score. IFEval checks
instructions rather than subjective writing quality. the BFCL subset is not its full
leaderboard. Harbor uses Inspect's ReAct agent, not Aider's agent or your own coding
agent. small subsets are smoke comparisons; increase sample counts and repeat runs
before drawing conclusions. these settings do not reproduce official leaderboards.

## setup

requires Python 3.12+ and an already-running server with an OpenAI-compatible chat
completions API. coding and agent presets also require a working Docker daemon and
Docker Compose. the benchmark computer runs the tests; the GPU can be elsewhere.

```bash
bash bench/setup.sh
python3 bench/run.py list
```

the first run downloads public datasets and, for coding tasks, container images.
Python packages are installed in `bench/.venv`; datasets and framework state use
`bench/.cache`. the upstream IFEval helper also caches NLTK data in
`~/.cache/nltk_data`. requirements pin framework versions; the selected tasks pin
their datasets, including immutable Harbor package references.

## run and compare

supply the server's API base URL and exact served model ID. labels distinguish
models and quantizations, while machine/details record the serving setup.

```bash
python3 bench/run.py run quick \
  --base-url http://gpu-a.local:8080/v1 --model model-a \
  --label model-a-q4 --machine gpu-a \
  --details 'q4, engine/version, 32k context, thinking enabled'

python3 bench/run.py run quick \
  --base-url http://gpu-b.local:8080/v1 --model model-b \
  --label model-b-q8 --machine gpu-b \
  --details 'q8, engine/version, 32k context, thinking enabled'

python3 bench/run.py run agent-coding \
  --base-url http://gpu-a.local:8080/v1 --model model-a \
  --label model-a-q4 --machine gpu-a --limit 5

python3 bench/run.py summary
python3 bench/run.py summary --csv > bench/results/comparison.csv
python3 bench/run.py view
```

the viewer is at `http://127.0.0.1:7575`; use `--port` if it is occupied. it shows
scores, individual answers, tool calls, errors and transcripts. each run has a
`run.json` manifest with package versions and model details beside its `.eval` logs.
results, caches, virtual environments and `*.local.json` configuration files are
gitignored. nothing is automatically added to registry recipes or published.

use `--api-key-file /path/to/key` for authenticated servers. credentials are read
inside the process, never put in command arguments or the manifest. `--dry-run`
prints evaluation settings without reading credentials, downloading tasks or
contacting a model.

## fair comparisons

defaults use a fixed shuffle seed of 42, temperature 0, one concurrent request,
8,192 output tokens per call, one retry for request failures and a 900-second sample
limit. agent tasks additionally have 30 turns and 32,768 total output tokens per
sample. native API tool calling is required; tool emulation is not enabled.

use the same preset, sample limit, seed, epochs and budgets for every model. the
report's `conditions` fingerprint covers these settings, runner source and installed
package versions. verify sample IDs in the logs too. record weight revisions,
quantization, engine version, context and thinking settings in `--details`; the
runner records these but cannot configure a remote server. different hardware will
affect timing independently of model quality.

`--limit 100 --epochs 3` gives a larger repeated comparison. the report preserves
all scorer metrics, standard errors where supplied, completed/planned sample counts
and errors. failed samples must not be treated as a clean capability score; a run
with evaluation errors exits nonzero. aborted tasks may have unattempted samples.

timing columns show median model-call latency and reported output tokens divided by
model-call time, including prompt processing and transport. they are not pure decode
speed or time to first token. missing usage stays unknown. compare timing on the
same tasks with similar output lengths, warm servers, and consistent server-side
cache settings. use a serving load benchmark separately for saturated throughput.

## local data

prompts go directly to the URL you supply, which should be a server you control.
answers, scores, manifests and transcripts stay on the benchmark computer. every
preset uses deterministic answer checks or local test execution; none uses a cloud
judge, hosted dashboard, or upload service. inherited Inspect telemetry/notification
settings are cleared, Hugging Face and Harbor telemetry are disabled, and unrelated dotenv files
are not loaded.

code and agent tools run in Docker with networking disabled. package/image builds
and public dataset downloads can use the internet before execution. the agent
preset adds pytest to the upstream image at build time, then disables package-index
access for grading. the task prompts, solutions and graders are unchanged. this
execution policy must stay the same across compared models. the viewer binds only
to loopback and renders untrusted transcript content as plain text.

Harbor also supports Terminal-Bench and repository repair suites. those need
task-specific dependency preparation before they can run with the same offline
policy; they are not included in these presets.

## verify the runner

```bash
bench/.venv/bin/python -m unittest discover -s bench -p 'test_*.py'
```

the integration test uses a synthetic local API and tiny fixtures. its results are
temporary and do not measure any real model's ability.

## reusable skill

[local-model-bench](skills/local-model-bench/SKILL.md) provides the workflow for
running these presets, comparing saved results, and keeping evaluation data local.
invoke it as `$local-model-bench` when installed in your skills directory.
