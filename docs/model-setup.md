# 本地模型安装 / Local model setup

改稿台调用本机的 `llama-server`，模型是上游训练的 [jialinyyzz/humanizer](https://huggingface.co/jialinyyzz/humanizer)。本项目编写了工作台、服务、校验与报告代码，没有自行训练这组权重。模型与 llama.cpp 由用户分别下载和安装，不随源码打包；训练数据也不在本仓库分发。上游权重和代码声明的许可不能作为所有用户稿件或上游训练材料的通用许可，见 [NOTICE](../NOTICE)。

下列命令是安装说明，不表示每个平台已经实测。真实运行结果以独立评测记录为准。当前没有商业检测器的真实测量，不能承诺改写后降分或通过检测。改写完成后仍须核对事实、引用、否定与适用范围。稿件不会自动发往外部检测器。

## 固定模型文件

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

从仓库根目录运行下面的下载命令；Windows 使用 `python`，Mac 通常使用 `python3`。`.local` 已被 Git 忽略。脚本需要完整的大小与 SHA-256，检查分段响应并支持恢复已校验的缓存分段，最终校验通过才发布完整文件。它只下载，不运行文件。新安装不需要 `--replace-invalid` 或 `--reuse-prefix`；已有不匹配文件会被保留并报错。可先查看 `python scripts/fetch_asset.py --help`。

```powershell
python scripts/fetch_asset.py "https://huggingface.co/jialinyyzz/humanizer/resolve/7232532cb8466bd393544e97826e12e6b5e471ac/humanizer-12b-IQ2_XS-QAT.gguf" ".local/models/humanizer-12b-IQ2_XS-QAT.gguf" --size 3893632896 --sha256 383e5ca8f1f48ab5f65013adbc1965fa70d1d1afa6c45d932c34b854e38edbb5
```

## Windows：NVIDIA CUDA 12.4

安装适用于本机 GPU 的 NVIDIA 驱动，并使用同一发布中的 CUDA 12.4 主程序和 CUDA 运行库压缩包。以下下载信息来自 [GitHub 官方发布元数据](https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/b11583)，核对日期为 2026-10-14。驱动与硬件兼容性请按 [NVIDIA CUDA 12.4 安装指南](https://docs.nvidia.com/cuda/archive/12.4.1/cuda-installation-guide-microsoft-windows/index.html)检查；已有兼容驱动的预编译运行，不等于必须为本项目编译完整 CUDA Toolkit。

```powershell
python scripts/fetch_asset.py "https://github.com/ggml-org/llama.cpp/releases/download/b11583/llama-b11583-bin-win-cuda-12.4-x64.zip" ".local/runtime/llama-b11583-bin-win-cuda-12.4-x64.zip" --size 265226766 --sha256 db709bfc5ee1a8eb34e03cf6cb5f936a985aaf8cd7b15af967e137c4a7d0191b
python scripts/fetch_asset.py "https://github.com/ggml-org/llama.cpp/releases/download/b11583/cudart-llama-bin-win-cuda-12.4-x64.zip" ".local/runtime/cudart-llama-bin-win-cuda-12.4-x64.zip" --size 391443627 --sha256 8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6
Expand-Archive -LiteralPath ".local/runtime/llama-b11583-bin-win-cuda-12.4-x64.zip" -DestinationPath ".local/runtime/b11583"
Expand-Archive -LiteralPath ".local/runtime/cudart-llama-bin-win-cuda-12.4-x64.zip" -DestinationPath ".local/runtime/b11583"
```

确认 CUDA DLL 与 `llama-server.exe` 同处于运行时目录；若压缩包带有不同顶层目录，需要按实际解压结构放置。选择那个目录内的程序启动，并仅绑定本机。先查找实际程序位置；把启动示例中的路径替换为查到的那个程序。

```powershell
Get-ChildItem -LiteralPath ".local/runtime/b11583" -Filter "llama-server.exe" -Recurse | Select-Object FullName
& "C:\path\to\llama-server.exe" -m ".local/models/humanizer-12b-IQ2_XS-QAT.gguf" -c 8192 -np 1 -ngl 99 --host 127.0.0.1 --port 8091
```

保留运行终端。启动日志应显示 CUDA 后端和实际卸载层数；若显存不足，减少 `-ngl`，并确认系统内存足够。`-ngl 0` 使用 CPU，速度可能较慢。如 GPU 驱动或 DLL 无法加载，可从同一官方发布选择 `llama-b11583-bin-win-cpu-x64.zip` 作为独立 CPU 运行时，避免用失败的 GPU 启动当作成功。

## Mac：Apple Silicon Metal / CPU

Apple Silicon 选择官方 `llama-b11583-bin-macos-arm64.tar.gz`；Intel Mac 选择 `llama-b11583-bin-macos-x64.tar.gz`。不要把 Windows CUDA 文件用于 Mac。官方 [构建说明](https://github.com/ggml-org/llama.cpp/blob/b11583/docs/build.md)说明 macOS 的 Metal 默认开启，`-ngl 0` 可在运行时关闭 GPU 推理。

| 压缩包 | 字节数 | SHA-256 |
| --- | --- | --- |
| `llama-b11583-bin-macos-arm64.tar.gz` | `12112217` | `d23832f4b847a722a64c9bf57e518c3df81dfab325942182ff17792d5d33351f` |
| `llama-b11583-bin-macos-x64.tar.gz` | `11608157` | `65f5da47373f28c4b53d68c257d9926cf5bd6e82172f7880fce6829307db2beb` |

Apple Silicon 示例：先运行前面的模型下载命令（把 `python` 改为 `python3`），再下载和解压运行时。

```bash
python3 scripts/fetch_asset.py "https://github.com/ggml-org/llama.cpp/releases/download/b11583/llama-b11583-bin-macos-arm64.tar.gz" ".local/runtime/llama-b11583-bin-macos-arm64.tar.gz" --size 12112217 --sha256 d23832f4b847a722a64c9bf57e518c3df81dfab325942182ff17792d5d33351f
mkdir -p .local/runtime/b11583
tar -xzf .local/runtime/llama-b11583-bin-macos-arm64.tar.gz -C .local/runtime/b11583
```

找到解压目录中的 `llama-server`，以实际路径替换下例中的 `/path/to/llama-server`。Apple Silicon 使用 `-ngl 99` 尝试 Metal；CPU 使用相同命令但改为 `-ngl 0`。统一内存仍需给 macOS 留出空间。

```bash
/path/to/llama-server -m .local/models/humanizer-12b-IQ2_XS-QAT.gguf -c 8192 -np 1 -ngl 99 --host 127.0.0.1 --port 8091
```

需要自己编译时，按官方固定标签构建，另行安装 CMake 和编译工具。Mac Metal 使用 `cmake -B build`；纯 CPU 可配置 `cmake -B build -DGGML_METAL=OFF`，随后 `cmake --build build --config Release`。此处没有声称 Mac 安装或推理已实测。

## 连接工作台与提示格式

在另一个终端检查 `http://127.0.0.1:8091/health`；只有返回 HTTP 200 且 `status` 为 `ok` 才表示模型已准备。服务启动本身不证明改写质量。工作台的默认模型地址就是该本机端口；如需更改，启动时设置 `PAPER_MODEL_URL` 为其他 loopback HTTP 地址。不要绑定到 `0.0.0.0`。

模型通过 `/completion` 处理文本。`src/paper_rewrite/model.py` 保留 [上游 prompt_format.json](https://huggingface.co/jialinyyzz/humanizer/blob/7232532cb8466bd393544e97826e12e6b5e471ac/prompt_format.json) 中的英文指令与分隔符，中文稿件也使用同一格式：`INSTRUCTION + "\n\n" + text.strip() + "\n\n### Rewritten:\n\n"`。没有 system 消息或对话轮次。温度为1.0、top-p为0.95、top-k和min-p为0、重复惩罚为1.0；不添加自定义 stop 字符串。来源及归属见 [上游项目](https://github.com/sgaofen/humanizer-local-model)与 [NOTICE](../NOTICE)。

应用的超时、截断或空输出会报告失败。不要把失败后的原文保留解释成模型改写成功；查看逐段状态与人工复核要求。模型 `/completion` 和 `/health` 的语义见 [llama.cpp 官方服务器说明](https://github.com/ggml-org/llama.cpp/blob/b11583/tools/server/README.md)。

## English quick equivalent

The model was trained upstream; this project provides the local workbench, checks, and reporting. Install llama.cpp and the model separately. The pinned IQ2 file above is a memory-constrained smoke-test choice for a 6 GB GPU, not a quality recommendation or a memory guarantee. Runtime memory exceeds the file size; higher precision usually needs more VRAM or RAM.

Use the verified downloader command from the repository root (`python3` on macOS). On Windows, download both b11583 CUDA 12.4 archives and place their runtime files together. On Apple Silicon, use the arm64 macOS archive with Metal; use `-ngl 0` for CPU. Run `llama-server` on `127.0.0.1:8091`, with `-c 8192 -np 1`, then verify `/health`. The app uses `/completion` and the original upstream completion prompt, without chat wrapping.

No manuscripts are automatically uploaded to a detector. Commercial detector measurements are still unavailable. Check facts and citations manually. Runtime, weights, user manuscripts, and training materials have separate licensing contexts; the project license does not grant rights to all of them.
