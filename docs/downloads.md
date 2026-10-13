# 下载与启动 / Download and start

GitHub Release 的源码 ZIP 包含已经构建的 `web/dist`，解压运行不需要 Node.js。它是带前端的 Python 应用源码包，不是 Windows 或 Mac 原生安装器。仍需安装 [uv](https://docs.astral.sh/uv/getting-started/installation/)，并由 uv 准备 Python 3.12；模型权重和 llama.cpp 运行时也需要按 [模型安装说明](model-setup.md)单独安装。初次安装依赖和模型需要网络。

下载发布页中同名的 `.zip` 和 `.zip.sha256`。先比较 ZIP 的 SHA-256 与校验文件，再解压到一个新目录。在 PowerShell 可用 `Get-FileHash -Algorithm SHA256`；Mac 可用 `shasum -a 256`。发布包附带 `bundle-manifest.json`，列出相对路径、文件大小和哈希，不含打包机器的绝对路径。

进入解压目录，先安装 Python 依赖，再启动本地工作台：

```text
uv sync --locked --no-dev --python 3.12
uv run --no-dev paper-rewrite serve --backend qwen --open
```

上述命令明确选择 Qwen。模型未启动时，工作台仍会打开，但改写会显示模型不可用。先按[模型安装说明](model-setup.md)在另一个终端启动 Qwen 的 `llama-server`，并确认 `http://127.0.0.1:8091/health` 正常，再进行改写。服务只绑定本机；稿件不会自动保存或上传到外部检测器。人工复核原文、数据和引用后再使用输出。

ZIP 不包含模型权重、CUDA、llama.cpp、密钥或用户稿件。换设备后需重新安装与硬件匹配的运行时。商业检测器未进行真实效果测量，不能把发布包视为降分保证。

## 维护者打包

先完成前端构建与项目检查，再确认应发布的源码已经加入 Git。打包脚本不会执行 npm、安装工具或构建前端；它只调用 Git 获取已跟踪文件清单，加上当下 `web/dist` 文件。无法凭文件存在证明前端最新，发布者必须在打包前完成构建。

```text
uv run --no-dev python scripts/build_bundle.py --output .local/release/paper-rewrite-source.zip
```

该命令拒绝覆盖已有 ZIP 或 `.sha256` 文件；请选择新文件名。脚本要求已跟踪的 LICENSE、NOTICE、README.md、pyproject.toml、uv.lock 和应用源码，以及已构建的 `web/dist/index.html`。未跟踪的其他文件不会被打包。模型文件、本地运行目录、Git 元数据和依赖目录被排除；敏感环境文件名及越界或符号链接会使打包失败。文件名检查不能替代发布前对源码的密钥与隐私审查。

同样的源文件与前端字节，在相同 Python 压缩运行环境下会产生相同 ZIP 字节；归档路径、顺序、时间戳与权限固定。相邻 SHA-256 文件由脚本独占创建。发布者应上传 ZIP 与校验文件，并在下载后再次核验；普通 GitHub 源码归档不包含被忽略的 `web/dist`，不能冒充该成品包。

## English quick start

Download the release ZIP and matching `.zip.sha256`, verify the checksum, and extract into a new directory. This is a source bundle with a prebuilt frontend, not a native installer. Node.js is unnecessary for end users; uv/Python 3.12 and a separately installed model/runtime are required.

Run `uv sync --locked --no-dev --python 3.12`, then `uv run --no-dev paper-rewrite serve --backend qwen --open`. This explicitly selects Qwen. Follow the [English model guide](model-setup.en.md) and start the local model before rewriting. Manuscripts are not automatically sent to an external detector. Review facts and citations yourself; commercial detector effectiveness is untested.

Maintainers build the frontend first, then use `uv run --no-dev python scripts/build_bundle.py --output .local/release/paper-rewrite-source.zip`. Only tracked source and prebuilt frontend files are included. Existing output is never overwritten. Review tracked content for secrets before publication.
