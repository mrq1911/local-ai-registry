# GTX 1080 Ti CUDA12 container evidence

The unchanged current-main registry lab ran on the owner's NVIDIA GeForce GTX 1080 Ti on 2026-10-17 UTC. All six gates passed: load, chat, reasoning, tools, context and speed. The raw run JSON and stock-generated 128K recipe were copied byte for byte.

| Measurement | Actual result |
| --- | --- |
| Context configuration | 131,072 tokens, one slot, f16 K/V cache |
| Logical / physical batch | 512 / 128 tokens |
| Context recall | 106,252 input tokens; correct code; 360.9 seconds |
| First 30-second streamed decode | 40.5 tokens/second |
| Complete uncapped streamed answer | 2,571 tokens in 68.3 seconds |
| Lab-reported prefill | 294 tokens/second |

The actual container used Docker 29.9.1 in WSL2 kernel 6.18.54.1-microsoft-standard-WSL2, with Windows NVIDIA driver 582.28. Windows, WSL and the container reported the same physical GTX1080Ti and 11,264 MiB total memory. Private records retain exact identity, model, image, local daemon/storage and owned-container cleanup checks. No peak model-only VRAM or per-layer offload measurement is claimed. Output was uncapped; no clock, power or fan change was used.

## Exact inputs and evidence

- Image: ghcr.io/ggml-org/llama.cpp:server-cuda12-b11146@sha256:52192a23c7b258044463aebba78826cdff39a7393b713edc313324b343a7b836.
- Weights: unsloth/Qwen3.5-9B-GGUF@3885219b6810b007914f3a7950a8d1b469d598a5; file Qwen3.5-9B-Q4_K_M.gguf; 5,680,522,464 bytes; SHA256 03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8.
- [Actual stock run JSON](../../lab-runs/gtx-1080-ti-11gb.qwen3.5-9b.llama.cpp-qwen3.5-9b-q4-k-m-128k-gtx1080ti-cuda12-ub128.128k.20261017T011654.json); raw-file SHA256 97b28d9e8a18f8bdbe367079fea7a265520410583ff75a3137940303a6b8dd16.
- Recipe log: sha256:3044d47683d60d33. The stock lab hashes its JSON text before appending the final newline, so its log hash differs from the raw-file checksum.
- Rendered launch SHA256: 3187fd54d4677c853e2448bc4a5bc54cdd750a879293a57020aaaf3b56e96e49.
- Exact measured current-main lab source is from b395198e77eb31138cd33a6b8a5beedef30b7c62; local measured LF file SHA256 40bf0d83d41cf6ce3d19fe39ebc12fde3283cd7768edddf16a3ec9e8961458c7. No gates, policy floors or exemptions were weakened.

This 11GB single-card profile advertises 132,096 KV tokens under the current stock calculation (131,072 context plus 1,024 for one slot), satisfying the 131,072-token floor for setups above 8GB. Actual six-gate success and local source integration are recorded here; generated-output freshness, full required checks and upstream CI are assessed separately. Maintainer reproduction, review and merge remain required. No payment or issuer acceptance is claimed.

Two preliminary 128K/f16 trials were stopped after prolonged lack of progress and severe desktop lag: one used default batching, and one already used batch512/ubatch128. Neither produced final gate proof; both private records are retained. Before this successful fresh run, competing desktop GPU load was removed and observed free video memory increased substantially. That was a changed operating condition, not a controlled demonstration of the stall's cause. This measured recipe uses logical batch512 and physical microbatch128; no memory-reduction guarantee is inferred from those settings.

The earlier 32K container run on 2026-10-17 genuinely passed its six measured gates at 23.5 tokens/second and 25,740 input tokens, but it did not satisfy the subsequently discovered current-main KV floor. Its raw evidence remains in data/lab-runs. It is historical evidence rather than the production recipe. [Native Windows measurements](../gtx1080ti-windows-cuda12/README.md) also remain supporting history. The maintainer [requested a plugin-runnable container and waived the kit reference panel/sweep](https://github.com/sybil-solutions/local-ai-registry/pull/276#issuecomment-6190931161); those waived tests are not claimed.

## Reproduction

Use Linux Docker Engine with NVIDIA Container Toolkit and the exact weights above. Set GPU218_MODEL_DIR to the checked model directory. This reproduces the measured image/arguments with a read-only input mount and loopback-only published endpoint. Proxy and API-key variables are cleared only for the lab command.

~~~bash
set -e
GPU218_MODEL_DIR=/path/to/Qwen3.5-9B-GGUF-3885219b
GPU218_IMAGE=ghcr.io/ggml-org/llama.cpp:server-cuda12-b11146@sha256:52192a23c7b258044463aebba78826cdff39a7393b713edc313324b343a7b836
printf '%s  %s\n' \
  03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8 \
  "$GPU218_MODEL_DIR/Qwen3.5-9B-Q4_K_M.gguf" | sha256sum -c -
docker pull "$GPU218_IMAGE"
GPU218_CID=$(docker create --gpus all --shm-size 16g \
  --publish 127.0.0.1:18082:8080 \
  --mount "type=bind,source=$GPU218_MODEL_DIR,target=/models,readonly" \
  --entrypoint /app/llama-server "$GPU218_IMAGE" \
  -m /models/Qwen3.5-9B-Q4_K_M.gguf --alias qwen3.5-9b \
  --host 0.0.0.0 --port 8080 --ctx-size 131072 --n-gpu-layers 999 \
  --flash-attn auto --cache-type-k f16 --cache-type-v f16 \
  --jinja --reasoning-format deepseek --parallel 1 \
  --batch-size 512 --ubatch-size 128)
trap 'docker logs "$GPU218_CID"; docker stop "$GPU218_CID"; docker rm "$GPU218_CID"' EXIT
docker start "$GPU218_CID"
curl --noproxy '*' --fail --retry 300 --retry-delay 3 --retry-connrefused \
  http://127.0.0.1:18082/health
env -u LAB_API_KEY -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u NO_PROXY \
  -u http_proxy -u https_proxy -u all_proxy -u no_proxy \
  python3 lab/lab.py try \
  unsloth/Qwen3.5-9B-GGUF@3885219b6810b007914f3a7950a8d1b469d598a5 \
  --model qwen3.5-9b --engine llama.cpp-qwen3.5-9b-q4-k-m-128k-gtx1080ti-cuda12-ub128 \
  --card gtx-1080-ti-11gb --on endpoint \
  --endpoint http://127.0.0.1:18082 --gpu 'NVIDIA GeForce GTX 1080 Ti'
~~~
