# Local model setup

Paper Rewrite runs a separately installed model through a local `llama-server`. This guide explicitly selects the **Qwen3.5-4B backend**; it does not assume which backend your installation uses by default. Qwen is a general instruction model, not a model trained specifically to lower detector scores. Paper Rewrite provides the workbench, document processing, checks and reports; it did not train the upstream weights.

The model download is about 3.14 GB and is separate from the application and llama.cpp runtime. Runtime memory also includes context, KV cache, working buffers and operating-system use: file size is not a RAM/VRAM requirement or a guarantee that a 6 GB GPU can run the configuration. Keep space for the download cache as well as the assembled file.

The commands below are installation instructions, not proof that every platform has been tested. **macOS installation and inference have not yet been tested for this project.** Actual recorded runs and limitations are in [evaluation.md](evaluation.md). No real commercial detector measurements are available, and no detector-score reduction or acceptance rate is promised. Review facts, citations, negation, uncertainty and scope manually. Drafts are not automatically uploaded to a detector.

## 1. Prepare the application

Install [uv using its official instructions](https://docs.astral.sh/uv/getting-started/installation/). Extract the release source bundle into a new directory and open a terminal there. The release bundle includes a built frontend; end users do not need Node.js. A plain Git checkout needs the frontend built separately before the browser workbench is available.

Run all following commands from the application root, where `pyproject.toml` and `scripts/` are located:

```sh
uv sync --locked --no-dev --python 3.12
```

This prepares Python 3.12 and the application dependencies. First installation requires internet access. The downloader commands below use `uv run --no-dev python`, so a separate system `python` or `python3` command is unnecessary. Downloads go into `.local/`, which is ignored by Git.

## 2. Download the pinned Qwen model

| Item | Pinned value |
| --- | --- |
| Official model | `Qwen/Qwen3.5-4B` |
| Official model revision | `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a` |
| GGUF provider | `unsloth/Qwen3.5-4B-GGUF` |
| GGUF revision | `e87f176479d0855a907a41277aca2f8ee7a09523` |
| File | `Qwen3.5-4B-Q5_K_M.gguf` |
| Size | `3143656608` bytes |
| SHA-256 | `8814232b85594dcd46c50e5b8b29324a7efe9e746edbe8a3d1df3d3fce7aad39` |
| llama.cpp runtime | `b11583` |

The size and checksum are from the [pinned GGUF metadata](https://huggingface.co/api/models/unsloth/Qwen3.5-4B-GGUF/revision/e87f176479d0855a907a41277aca2f8ee7a09523?blobs=true). Only the text model is needed; do not download a vision projection model for this workbench.

The following command works in PowerShell and macOS shells:

```sh
uv run --no-dev python scripts/fetch_asset.py "https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/e87f176479d0855a907a41277aca2f8ee7a09523/Qwen3.5-4B-Q5_K_M.gguf" ".local/models/Qwen3.5-4B-Q5_K_M.gguf" --size 3143656608 --sha256 8814232b85594dcd46c50e5b8b29324a7efe9e746edbe8a3d1df3d3fce7aad39
```

The downloader validates HTTP byte ranges, resumes verified cached parts and publishes the complete file only after checking its size and SHA-256. It downloads files without executing them. On a fresh install, do not add `--replace-invalid` or `--reuse-prefix`: a mismatched existing file is preserved and reported as an error. To inspect options, run `uv run --no-dev python scripts/fetch_asset.py --help`.

## 3A. Windows with an NVIDIA GPU

Use a compatible NVIDIA driver and both CUDA 12.4 archives from the same [official llama.cpp b11583 release](https://github.com/ggml-org/llama.cpp/releases/tag/b11583). These published archive values were checked on 2026-10-14 in the [official release metadata](https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/b11583). Check driver and hardware compatibility against [NVIDIA's CUDA 12.4 Windows guide](https://docs.nvidia.com/cuda/archive/12.4.1/cuda-installation-guide-microsoft-windows/index.html). Running these prebuilt binaries with a compatible driver does not by itself require building or installing the entire CUDA Toolkit.

```powershell
uv run --no-dev python scripts/fetch_asset.py "https://github.com/ggml-org/llama.cpp/releases/download/b11583/llama-b11583-bin-win-cuda-12.4-x64.zip" ".local/runtime/llama-b11583-bin-win-cuda-12.4-x64.zip" --size 265226766 --sha256 db709bfc5ee1a8eb34e03cf6cb5f936a985aaf8cd7b15af967e137c4a7d0191b
uv run --no-dev python scripts/fetch_asset.py "https://github.com/ggml-org/llama.cpp/releases/download/b11583/cudart-llama-bin-win-cuda-12.4-x64.zip" ".local/runtime/cudart-llama-bin-win-cuda-12.4-x64.zip" --size 391443627 --sha256 8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6
Expand-Archive -LiteralPath ".local/runtime/llama-b11583-bin-win-cuda-12.4-x64.zip" -DestinationPath ".local/runtime/b11583"
Expand-Archive -LiteralPath ".local/runtime/cudart-llama-bin-win-cuda-12.4-x64.zip" -DestinationPath ".local/runtime/b11583"
Get-ChildItem -LiteralPath ".local/runtime/b11583" -Filter "llama-server.exe" -Recurse | Select-Object FullName
```

Ensure the CUDA runtime DLLs are alongside `llama-server.exe`; archives may have different top-level folders. Replace `C:\path\to\llama-server.exe` below with the actual path listed above, then start the model:

```powershell
& "C:\path\to\llama-server.exe" -m ".local/models/Qwen3.5-4B-Q5_K_M.gguf" --alias qwen3.5-4b -c 4096 -np 1 -ngl 99 -b 128 -ub 64 --host 127.0.0.1 --port 8091 --no-ui --cors-origins http://127.0.0.1:8765 --no-cors-credentials
```

Keep this terminal open. Confirm that startup logs identify the CUDA backend and the actual number of offloaded layers. If VRAM is insufficient, reduce `-ngl` and ensure sufficient system RAM. `-ngl 0` uses CPU inference and may be slower. If CUDA drivers or DLLs cannot load, the same official release offers `llama-b11583-bin-win-cpu-x64.zip` as a separate CPU runtime; obtain it from that release and verify its published metadata. No unverified CPU-archive checksum is supplied here.

## 3B. macOS with Metal or CPU

For Apple Silicon, download the arm64 archive:

```sh
uv run --no-dev python scripts/fetch_asset.py "https://github.com/ggml-org/llama.cpp/releases/download/b11583/llama-b11583-bin-macos-arm64.tar.gz" ".local/runtime/llama-b11583-bin-macos-arm64.tar.gz" --size 12112217 --sha256 d23832f4b847a722a64c9bf57e518c3df81dfab325942182ff17792d5d33351f
mkdir -p .local/runtime/b11583
tar -xzf .local/runtime/llama-b11583-bin-macos-arm64.tar.gz -C .local/runtime/b11583
```

For an Intel Mac, use the x64 archive instead:

```sh
uv run --no-dev python scripts/fetch_asset.py "https://github.com/ggml-org/llama.cpp/releases/download/b11583/llama-b11583-bin-macos-x64.tar.gz" ".local/runtime/llama-b11583-bin-macos-x64.tar.gz" --size 11608157 --sha256 65f5da47373f28c4b53d68c257d9926cf5bd6e82172f7880fce6829307db2beb
mkdir -p .local/runtime/b11583
tar -xzf .local/runtime/llama-b11583-bin-macos-x64.tar.gz -C .local/runtime/b11583
```

Locate the extracted `llama-server` and substitute its actual path for `/path/to/llama-server`. Do not use the Windows CUDA archives on macOS. On Apple Silicon, this command attempts Metal inference:

```sh
/path/to/llama-server -m .local/models/Qwen3.5-4B-Q5_K_M.gguf --alias qwen3.5-4b -c 4096 -np 1 -ngl 99 -b 128 -ub 64 --host 127.0.0.1 --port 8091 --no-ui --cors-origins http://127.0.0.1:8765 --no-cors-credentials
```

For CPU inference, including the Intel Mac path, change `-ngl 99` to `-ngl 0`. Leave enough unified/system memory for macOS and other applications. Keep the model terminal open. This project has not verified these macOS installation or inference paths.

If compiling instead, follow the [fixed-tag llama.cpp build instructions](https://github.com/ggml-org/llama.cpp/blob/b11583/docs/build.md) with CMake and compiler tools installed. In a b11583 source checkout, use `cmake -B build` for the macOS Metal configuration or `cmake -B build -DGGML_METAL=OFF` for CPU, then `cmake --build build --config Release`.

## 4. Check readiness and open the workbench

Only one model should use port 8091 at a time. Stop an earlier model server before switching models. In a second terminal, verify readiness:

```powershell
Invoke-RestMethod "http://127.0.0.1:8091/health"
```

On macOS, use:

```sh
curl -f http://127.0.0.1:8091/health
```

The response must be HTTP 200 with `status` equal to `ok`. A process starting is not enough. Readiness also does not prove rewriting quality.

Start the application in the second terminal, from the application root:

```sh
uv run --no-dev paper-rewrite serve --backend qwen --open
```

The workbench opens at `http://127.0.0.1:8765`. Choose the interface language and the manuscript language separately. Review the paragraph checks and unused candidates. You can edit the output and recheck it; edited text invalidates previous detector reports and consent. External detection requires an explicit action and consent and may incur charges.

The Qwen backend sends `/v1/chat/completions` requests with model name `qwen3.5-4b`, matching the runtime's `--alias`. If you previously configured `PAPER_MODEL_NAME`, remove that override or set it to `qwen3.5-4b`. `PAPER_MODEL_URL` can select another loopback HTTP origin at startup; its normal address is `http://127.0.0.1:8091`. Keep both services bound to `127.0.0.1`, not `0.0.0.0`. The runtime flags disable its separate web UI and restrict CORS to the workbench origin shown above.

The application explicitly disables thinking using `chat_template_kwargs={"enable_thinking": false}`. Its editing instruction preserves facts, protected terms, negation, uncertainty and proposed-versus-completed status. Truncated, empty, invalid or reasoning-contaminated replies are recorded as failures. Default Qwen sampling uses temperature 0.7, top-p 0.8, top-k 20, min-p 0, presence penalty 1.5 and repetition penalty 1.0, following the [official non-thinking guidance](https://huggingface.co/Qwen/Qwen3.5-4B#best-practices).

## CLI use and recorded evaluation

With the model server still running, rewrite a UTF-8 text or Markdown file:

```sh
uv run --no-dev paper-rewrite rewrite draft.txt -o revised.txt --report review.json --backend qwen --language en --keep BM25
```

Use `--language zh` for Chinese and repeat `--keep` for additional verbatim terms. Choose new output/report filenames: the CLI refuses to overwrite existing files or the source. Limits are 12000 source characters, 60 prose paragraphs, 1000 characters per prose paragraph and 1–3 candidates per paragraph (`--candidates 2` is the normal setting). Structural Markdown and references are preserved. A partially retained or unchanged document is not a fully successful rewrite; a wholly failed model run creates no rewritten file.

To run the synthetic methods-draft corpus and record the model file hash:

```sh
uv run --no-dev python scripts/evaluate.py --backend qwen --corpus data/prose.jsonl --output artifacts/my-qwen-run.json --model-file .local/models/Qwen3.5-4B-Q5_K_M.gguf --model-repo unsloth/Qwen3.5-4B-GGUF --model-revision e87f176479d0855a907a41277aca2f8ee7a09523 --runtime "llama.cpp b11583; add your actual hardware"
```

The evaluation output path must also be new. Synthetic examples are not real research findings, human-authored papers or evidence of detector effectiveness. The model name, repository/revision and runtime description are operator-supplied labels. A local file hash does not prove that an HTTP server loaded that file; reports retain `backend_identity_verification: not_verified`.

## Optional humanizer comparison

The upstream humanizer completion model uses a different prompt and `/completion` API. The pinned memory-constrained IQ2 smoke-test configuration is `jialinyyzz/humanizer`, revision `7232532cb8466bd393544e97826e12e6b5e471ac`, file `humanizer-12b-IQ2_XS-QAT.gguf`, size `3893632896` bytes, SHA-256 `383e5ca8f1f48ab5f65013adbc1965fa70d1d1afa6c45d932c34b854e38edbb5`.

```sh
uv run --no-dev python scripts/fetch_asset.py "https://huggingface.co/jialinyyzz/humanizer/resolve/7232532cb8466bd393544e97826e12e6b5e471ac/humanizer-12b-IQ2_XS-QAT.gguf" ".local/models/humanizer-12b-IQ2_XS-QAT.gguf" --size 3893632896 --sha256 383e5ca8f1f48ab5f65013adbc1965fa70d1d1afa6c45d932c34b854e38edbb5
```

Stop Qwen, restart the same platform-specific `llama-server` with this model file instead, and omit the Qwen-specific `--alias qwen3.5-4b`. Then run `uv run --no-dev paper-rewrite serve --backend humanizer --open` or use `--backend humanizer` in the rewrite command. Remove any Qwen-specific `PAPER_MODEL_NAME` override when switching. The application retains the [upstream completion prompt](https://huggingface.co/jialinyyzz/humanizer/blob/7232532cb8466bd393544e97826e12e6b5e471ac/prompt_format.json), including its English instruction and `### Rewritten:` separator, for both English and Chinese inputs. Protected terms are checked after generation rather than inserted into that fixed prompt.

IQ2 was chosen for constrained hardware experiments, not as a final writing-quality recommendation or a memory guarantee. See [evaluation.md](evaluation.md) for failures and retained-source cases rather than assuming that every generated candidate was accepted.

## Sources and rights

[Qwen's official model card](https://huggingface.co/Qwen/Qwen3.5-4B) and [Unsloth's quantized model card](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF) declare Apache-2.0; llama.cpp uses its own MIT license, and other runtime components retain their respective licenses. See [NOTICE](../NOTICE) for attribution and upstream humanizer notices. These licenses do not grant blanket rights to user manuscripts, citations or upstream training materials. This project does not redistribute model weights or training datasets, claim ownership of upstream training, or imply endorsement by model or detector providers.
