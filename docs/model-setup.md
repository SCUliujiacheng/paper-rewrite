# 本地模型安装

本指南明确选择 [Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B) 后端，不依赖安装环境的默认后端。它是通用指令模型，不是专门训练来降低检测分数的模型。改稿台提供工作台、文档处理、校验与报告，没有自行训练上游权重。模型与 llama.cpp 分别安装，不随源码打包；训练数据不在本仓库分发。上游许可不授予用户稿件或训练材料的通用权利，归属见 [NOTICE](../NOTICE)。

**本项目尚未验证 Mac 安装与推理。** 下列命令是安装说明，不表示每个平台已经实测。真实运行结果见[评测说明](evaluation.md)。当前没有商业检测器的真实测量，不能承诺改写后降分或通过检测。改写完成后仍须核对事实、引用、否定与适用范围。稿件不会自动发往外部检测器。


英文完整步骤见 [English guide](model-setup.en.md)。

## 1. 准备应用

按[官方说明安装 uv](https://docs.astral.sh/uv/getting-started/installation/)，将发布 ZIP 解压到新目录，在包含 `pyproject.toml` 与 `scripts/` 的应用根目录打开终端。发布 ZIP 已有构建好的前端，无需 Node.js；普通 Git 源码检出需要另行构建前端。

```sh
uv sync --locked --no-dev --python 3.12
```

这会准备 Python 3.12 和依赖。下文统一使用 `uv run --no-dev python`，不用另找系统 Python。首次安装需要网络；请给分段缓存和完整模型文件都留出磁盘空间。文件大小不等于运行内存，还需上下文、KV 缓存、工作缓冲和系统内存，不能保证6 GB显存适用。

## 2. 下载固定版本 Qwen

这是通用指令模型，不是专门训练来降低检测分数的模型。本指南使用该后端进行本地学术编辑。GGUF 由 Unsloth 提供；官方模型卡与量化模型卡均声明 Apache-2.0。模型卡说明可用范围不等于本项目效果证明，真实输出另见[测试记录](evaluation.md)。

| 项目 | 固定值 |
| --- | --- |
| 官方模型 | `Qwen/Qwen3.5-4B` |
| 官方修订 | `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a` |
| GGUF 仓库 | `unsloth/Qwen3.5-4B-GGUF` |
| GGUF 修订 | `e87f176479d0855a907a41277aca2f8ee7a09523` |
| 文件 | `Qwen3.5-4B-Q5_K_M.gguf` |
| 大小 | `3143656608` 字节 |
| SHA-256 | `8814232b85594dcd46c50e5b8b29324a7efe9e746edbe8a3d1df3d3fce7aad39` |

文件信息来自[固定修订元数据](https://huggingface.co/api/models/unsloth/Qwen3.5-4B-GGUF/revision/e87f176479d0855a907a41277aca2f8ee7a09523?blobs=true)。不需要下载图像投影模型；这个工作台只处理文本。

```text
uv run --no-dev python scripts/fetch_asset.py "https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/e87f176479d0855a907a41277aca2f8ee7a09523/Qwen3.5-4B-Q5_K_M.gguf" ".local/models/Qwen3.5-4B-Q5_K_M.gguf" --size 3143656608 --sha256 8814232b85594dcd46c50e5b8b29324a7efe9e746edbe8a3d1df3d3fce7aad39
```

## 3A. Windows：NVIDIA CUDA 12.4

安装适用于本机 GPU 的 NVIDIA 驱动，并使用同一发布中的 CUDA 12.4 主程序和 CUDA 运行库压缩包。以下下载信息来自 [GitHub 官方发布元数据](https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/b11583)，核对日期为 2026-10-14。驱动与硬件兼容性请按 [NVIDIA CUDA 12.4 安装指南](https://docs.nvidia.com/cuda/archive/12.4.1/cuda-installation-guide-microsoft-windows/index.html)检查；已有兼容驱动的预编译运行，不等于必须为本项目编译完整 CUDA Toolkit。

```powershell
uv run --no-dev python scripts/fetch_asset.py "https://github.com/ggml-org/llama.cpp/releases/download/b11583/llama-b11583-bin-win-cuda-12.4-x64.zip" ".local/runtime/llama-b11583-bin-win-cuda-12.4-x64.zip" --size 265226766 --sha256 db709bfc5ee1a8eb34e03cf6cb5f936a985aaf8cd7b15af967e137c4a7d0191b
uv run --no-dev python scripts/fetch_asset.py "https://github.com/ggml-org/llama.cpp/releases/download/b11583/cudart-llama-bin-win-cuda-12.4-x64.zip" ".local/runtime/cudart-llama-bin-win-cuda-12.4-x64.zip" --size 391443627 --sha256 8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6
Expand-Archive -LiteralPath ".local/runtime/llama-b11583-bin-win-cuda-12.4-x64.zip" -DestinationPath ".local/runtime/b11583"
Expand-Archive -LiteralPath ".local/runtime/cudart-llama-bin-win-cuda-12.4-x64.zip" -DestinationPath ".local/runtime/b11583"
```

确认 CUDA DLL 与 `llama-server.exe` 同处于运行时目录；若压缩包带有不同顶层目录，需要按实际解压结构放置。选择那个目录内的程序启动，并仅绑定本机。先查找实际程序位置；把启动示例中的路径替换为查到的那个程序。

```powershell
Get-ChildItem -LiteralPath ".local/runtime/b11583" -Filter "llama-server.exe" -Recurse | Select-Object FullName
& "C:\path\to\llama-server.exe" -m ".local/models/Qwen3.5-4B-Q5_K_M.gguf" --alias qwen3.5-4b -c 4096 -np 1 -ngl 99 -b 128 -ub 64 --host 127.0.0.1 --port 8091 --no-ui --cors-origins http://127.0.0.1:8765 --no-cors-credentials
```

保留运行终端。启动日志应显示 CUDA 后端和实际卸载层数；若显存不足，减少 `-ngl`，并确认系统内存足够。`-ngl 0` 使用 CPU，速度可能较慢。如 GPU 驱动或 DLL 无法加载，可从同一官方发布选择 `llama-b11583-bin-win-cpu-x64.zip` 作为独立 CPU 运行时，避免用失败的 GPU 启动当作成功。

## 3B. Mac：Metal 或 CPU

Apple Silicon 选择官方 `llama-b11583-bin-macos-arm64.tar.gz`；Intel Mac 选择 `llama-b11583-bin-macos-x64.tar.gz`。不要把 Windows CUDA 文件用于 Mac。官方 [构建说明](https://github.com/ggml-org/llama.cpp/blob/b11583/docs/build.md)说明 macOS 的 Metal 默认开启，`-ngl 0` 可在运行时关闭 GPU 推理。

| 压缩包 | 字节数 | SHA-256 |
| --- | --- | --- |
| `llama-b11583-bin-macos-arm64.tar.gz` | `12112217` | `d23832f4b847a722a64c9bf57e518c3df81dfab325942182ff17792d5d33351f` |
| `llama-b11583-bin-macos-x64.tar.gz` | `11608157` | `65f5da47373f28c4b53d68c257d9926cf5bd6e82172f7880fce6829307db2beb` |

Apple Silicon 使用下列 arm64 压缩包；Intel Mac 使用表中的 x64 压缩包。模型下载和依赖准备仍使用前面的 uv 命令。

```bash
uv run --no-dev python scripts/fetch_asset.py "https://github.com/ggml-org/llama.cpp/releases/download/b11583/llama-b11583-bin-macos-arm64.tar.gz" ".local/runtime/llama-b11583-bin-macos-arm64.tar.gz" --size 12112217 --sha256 d23832f4b847a722a64c9bf57e518c3df81dfab325942182ff17792d5d33351f
mkdir -p .local/runtime/b11583
tar -xzf .local/runtime/llama-b11583-bin-macos-arm64.tar.gz -C .local/runtime/b11583
```

Intel Mac 下载与解压命令：

```sh
uv run --no-dev python scripts/fetch_asset.py "https://github.com/ggml-org/llama.cpp/releases/download/b11583/llama-b11583-bin-macos-x64.tar.gz" ".local/runtime/llama-b11583-bin-macos-x64.tar.gz" --size 11608157 --sha256 65f5da47373f28c4b53d68c257d9926cf5bd6e82172f7880fce6829307db2beb
mkdir -p .local/runtime/b11583
tar -xzf .local/runtime/llama-b11583-bin-macos-x64.tar.gz -C .local/runtime/b11583
```

Intel Mac 或纯 CPU 使用 `-ngl 0`。Mac 安装与推理尚未在本项目验证。

找到解压目录中的 `llama-server`，以实际路径替换下例中的 `/path/to/llama-server`。Apple Silicon 使用 `-ngl 99` 尝试 Metal；CPU 使用相同命令但改为 `-ngl 0`。统一内存仍需给 macOS 留出空间。

```bash
/path/to/llama-server -m .local/models/Qwen3.5-4B-Q5_K_M.gguf --alias qwen3.5-4b -c 4096 -np 1 -ngl 99 -b 128 -ub 64 --host 127.0.0.1 --port 8091 --no-ui --cors-origins http://127.0.0.1:8765 --no-cors-credentials
```

需要自己编译时，按官方固定标签构建，另行安装 CMake 和编译工具。Mac Metal 使用 `cmake -B build`；纯 CPU 可配置 `cmake -B build -DGGML_METAL=OFF`，随后 `cmake --build build --config Release`。此处没有声称 Mac 安装或推理已实测。

## 4. 检查模型并打开工作台

同一时间只让一个模型使用8091端口，切换前先停止旧服务。在另一个终端检查：

```powershell
Invoke-RestMethod "http://127.0.0.1:8091/health"
```

Mac 使用 `curl -f http://127.0.0.1:8091/health`。必须返回 HTTP 200 且 `status` 为 `ok`；启动不代表就绪，就绪也不证明改写质量。然后在应用根目录运行：

```sh
uv run --no-dev paper-rewrite serve --backend qwen --open
```

工作台打开于 `http://127.0.0.1:8765`。界面语言和稿件语言分别选择，检查逐段结果与未采用候选。人工编辑后可重新核对，旧检测报告与授权会失效。外部检测需要明确操作与同意，可能产生费用。

Qwen 通过 `/v1/chat/completions` 和模型自身模板工作。名称 `qwen3.5-4b` 对应运行时的 `--alias`；已有 `PAPER_MODEL_NAME` 覆盖时应移除或改为该名称。`PAPER_MODEL_URL` 可在启动时选择其他 loopback HTTP 地址；两个服务都只绑定 `127.0.0.1`。运行时参数关闭其独立网页并限制 CORS；修改工作台端口时也应调整允许来源。

应用显式设置 `chat_template_kwargs={"enable_thinking": false}`，编辑指令保留事实、保护词、否定、不确定性及拟议/已完成状态。默认温度0.7、top-p 0.8、top-k 20、min-p 0、presence penalty 1.5、重复惩罚1.0，遵循[官方非思考通用配置](https://huggingface.co/Qwen/Qwen3.5-4B#best-practices)。截断、空内容、无效或混入思考内容的回复记录为失败。

## CLI 与评测记录

模型保持运行时，可处理 UTF-8 文本或 Markdown：

```sh
uv run --no-dev paper-rewrite rewrite draft.txt -o revised.txt --report review.json --backend qwen --language zh --keep BM25
```

英文用 `--language en`，额外术语重复 `--keep`。输出和报告必须是新文件名，CLI 不覆盖原稿或已有文件。限制为12000字符、60段、每个可改写段落1000字符及1–3个候选（通常为2）。Markdown 结构和参考文献保留；部分保留或未变更不等于整篇改写成功，全部模型失败时不生成改写文件。

运行合成方法初稿，并记录实际模型文件哈希：

```sh
uv run --no-dev python scripts/evaluate.py --backend qwen --corpus data/prose.jsonl --output artifacts/my-qwen-run.json --model-file .local/models/Qwen3.5-4B-Q5_K_M.gguf --model-repo unsloth/Qwen3.5-4B-GGUF --model-revision e87f176479d0855a907a41277aca2f8ee7a09523 --runtime "llama.cpp b11583; add your actual hardware"
```

结果路径也必须是新的。合成语料不是研究成果、人类论文或检测效果证据。模型名、仓库修订和运行时描述是操作者提供的标签；本地文件哈希不证明 HTTP 服务加载了它，报告保留 `backend_identity_verification: not_verified`。

## 可选 humanizer 对照

本次冒烟配置用于尝试适配 6 GB NVIDIA 显存，选择最小的 IQ2 文件；这是硬件条件下的测试选择，不是推荐的最终写作质量设置。文件大小不等于运行内存：上下文、KV 缓存、工作缓冲和系统占用还会增加需求，6 GB 也不保证全部加载成功。更高量化文件通常需要更多显存或系统内存，CPU 分担也会影响速度。请结合自己的硬件复核，不照搬上游其他机器的性能数字。

| 项目 | 固定值 |
| --- | --- |
| 模型仓库 | `jialinyyzz/humanizer` |
| 修订 | `7232532cb8466bd393544e97826e12e6b5e471ac` |
| 文件 | `humanizer-12b-IQ2_XS-QAT.gguf` |
| 大小 | `3893632896` 字节 |
| SHA-256 | `383e5ca8f1f48ab5f65013adbc1965fa70d1d1afa6c45d932c34b854e38edbb5` |
| 运行时 | llama.cpp `b11583` |

出处：[固定修订的模型文件](https://huggingface.co/jialinyyzz/humanizer/tree/7232532cb8466bd393544e97826e12e6b5e471ac)、[Hugging Face 文件元数据](https://huggingface.co/api/models/jialinyyzz/humanizer/revision/7232532cb8466bd393544e97826e12e6b5e471ac?blobs=true)、[llama.cpp b11583 官方发布](https://github.com/ggml-org/llama.cpp/releases/tag/b11583)。

从应用根目录使用已经准备好的 uv 环境下载。`.local` 已被 Git 忽略。脚本需要完整的大小与 SHA-256，检查分段响应并支持恢复已校验的缓存分段，最终校验通过才发布完整文件。它只下载，不运行文件。新安装不需要 `--replace-invalid` 或 `--reuse-prefix`；已有不匹配文件会被保留并报错。可先查看 `uv run --no-dev python scripts/fetch_asset.py --help`。

```powershell
uv run --no-dev python scripts/fetch_asset.py "https://huggingface.co/jialinyyzz/humanizer/resolve/7232532cb8466bd393544e97826e12e6b5e471ac/humanizer-12b-IQ2_XS-QAT.gguf" ".local/models/humanizer-12b-IQ2_XS-QAT.gguf" --size 3893632896 --sha256 383e5ca8f1f48ab5f65013adbc1965fa70d1d1afa6c45d932c34b854e38edbb5
```

停止 Qwen 后，使用对应平台的同一个 `llama-server`，将模型路径换成 humanizer 文件并去掉 Qwen 的 `--alias qwen3.5-4b`。移除 Qwen 专用的 `PAPER_MODEL_NAME` 覆盖，然后运行 `uv run --no-dev paper-rewrite serve --backend humanizer --open`，或在改写命令指定 `--backend humanizer`。

`--backend humanizer` 通过 `/completion` 处理文本。`src/paper_rewrite/model.py` 保留 [上游 prompt_format.json](https://huggingface.co/jialinyyzz/humanizer/blob/7232532cb8466bd393544e97826e12e6b5e471ac/prompt_format.json) 中的英文指令与分隔符，中文稿件也使用同一格式：`INSTRUCTION + "\n\n" + text.strip() + "\n\n### Rewritten:\n\n"`。没有 system 消息或对话轮次，保护词在生成后由检查器核对，不插入上游固定提示。温度为1.0、top-p为0.95、top-k和min-p为0、重复惩罚为1.0；不添加自定义 stop 字符串。评测脚本可用 `--temperature` 做独立采样对照，报告记录实际值。来源及归属见 [上游项目](https://github.com/sgaofen/humanizer-local-model)与 [NOTICE](../NOTICE)。



## 来源与权利

[Qwen 官方模型卡](https://huggingface.co/Qwen/Qwen3.5-4B)和 [Unsloth 量化模型卡](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF)声明 Apache-2.0；llama.cpp 使用 MIT，其他运行组件保留各自许可。归属见 [NOTICE](../NOTICE)，接口见[官方服务器说明](https://github.com/ggml-org/llama.cpp/blob/b11583/tools/server/README.md)。这些许可不授予所有稿件、引用或上游训练材料的通用权利。本项目不分发模型权重与训练数据，也不宣称拥有上游训练成果或获得供应商背书。
