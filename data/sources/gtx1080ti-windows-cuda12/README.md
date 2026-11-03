# GTX 1080 Ti native Windows supporting evidence

Historical owner-card measurements. The production recipe now uses the measured [Linux CUDA12 container](../gtx1080ti-cuda12-container/README.md), which passed all six unchanged registry lab gates on 2026-10-17.

Actual local trial on 2026-10-15, using the unchanged registry lab at a7769baeccb11a97ba3abc57aeedca645672eeea. The owner GTX 1080 Ti ran Qwen3.5-9B Q4_K_M at 32,768 context. All six gates passed; first-30-second decode was 37.5 tok/s, near-full recall used25,740 input tokens, and uncapped generation completed10,161tokens. Desktop applications remained running. These are supporting local measurements, not an isolated recipe-kit acceptance.

## Evidence

- `../../lab-runs/gtx-1080-ti-11gb.qwen3.5-9b.llama.cpp-qwen3.5-9b-q4-k-m-32k-gtx1080ti-windows-cuda12.32k.20261015T090343.json`: normalized UTF8/LF lab output, measured values unchanged; proof payload SHA256 c00ab71bb95a6500d820caff6f1c0d405a1b00ac10b4ccf8cc16027226932a29. The original WindowsCP1252/CRLF output is preserved privately alongside the trial evidence.
- `probe.windows-supporting.json`: Windows physical RAM and whole-device nvidia-smi probe from08:53UTC before the run. It is not the Linux kit probe and provides no swap, NVMe bandwidth or reference-panel claim.
- `memwatch.windows-supporting.csv`:374 one-second samples started before the server. Whole-device peak7,526MiB includes unrelated Windows desktop activity; available physical RAM fell from47.24789GB to39.79923GB.
- `windows_measure.py`: exact supporting probe/watcher source. Read-only measurements; no clock, power, fan or other process controls.

## Reproduction boundaries

Official llama.cpp b11146, source7fe450e19305b828c199d602c23a8337aaa1f03b, WindowsCUDA12.4 binaries and DLLs. BinaryZIP SHA2563c806a6ceccc3dae1c743ceb1a1fb2cce5b76f40bfbd4c6b7b8afb6ef45a5807; DLLZIP SHA2568c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6. GGUF unsloth/Qwen3.5-9B-GGUF revision3885219b6810b007914f3a7950a8d1b469d598a5, file SHA25603b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8.

No output caps, clock/power/fan changes or disabled CUDA graphs. Use explicit Python `-X utf8` on Windows to avoid locale-dependent evidence/profile hashes. Future controlled runs select an F: CUDA cache; the original run did not explicitly set that path. Nothing here claims that a GPU test was rerun after preparation changes.

The card metadata field bandwidth_gb_s484 is the manufacturer specification, not a measurement from this trial: https://developer.nvidia.com/blog/nvidia-turing-architecture-in-depth/ (GTX1080Ti comparison table).

The maintainer requested a plugin-runnable Linux container replacement and waived the kit reference panel/sweep for this rentable card. That separate container run and its exact evidence are documented in the linked README. This directory retains the original Windows evidence; its values were not substituted for the container measurements.
