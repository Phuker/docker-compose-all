# 项目概览

docker-compose-all 是一个 Python CLI 工具，递归扫描目录（默认 `.`）下的所有 Docker Compose 项目，并在每个项目目录中批量执行 `docker compose` 命令。

包结构单一，纯标准库实现（`pyproject.toml` 的 `dependencies` 为空，与用户确认后才可以引入第三方依赖）：

- `docker_compose_all/docker_compose_all.py`：全部核心逻辑与 CLI 入口
- `docker_compose_all/__init__.py`：唯一版本来源 `__version__`
- `docker_compose_all/__main__.py`：`python -m docker_compose_all` 入口

# 设计细节

- 调用的是 `docker compose`（`docker` 子命令），不是旧版 `docker-compose`。
- 扫描目录来自 `--dca-scan-dir`（默认 `.`）；`scan_dirs()` 会 `os.walk(..., followlinks=True)`，软链接可能造成重复扫描；项目识别依据文件名：`compose.yaml` / `compose.yml` / `docker-compose.yaml` / `docker-compose.yml`。
- `shell_args`、`error_info_list` 为模块级全局可变状态。
- 日志输出到 stdout（`init_logging()` 设 `stream=sys.stdout`），不是 stderr，日志与 `docker compose` 子进程输出同流交织。
- 将各项目的 `dir_path` 作为 `cwd` 参数传入 `subprocess.check_call()`，不改变当前进程 cwd，无 cwd 副作用。
- `cleanup()` 由 `--dca-cleanup` 触发，对应 `COMMANDS_CLEANUP` / `COMMAND_CLEANUP_*`，依次执行 `docker network/image/builder prune -f`，仅在全部项目命令成功（`error_info_list` 为空）时执行；存在错误时跳过并告警。清理命令用 `subprocess.call` 执行，返回码被忽略。
- 非 root 只告警不退出（`logger.warning('Not running as root')`）。
- 校验不用 `assert` 语句，统一用 `assert_()` 抛 `AssertionError`（避免 `python -O` 下被忽略）。

## 日志颜色与字重

日志正文用 `colored()` 着色，目标：主/次分明、总/分分明、内部一致；只局部高亮正文中的值，其余文本保持普通样式。日志 `[LEVEL]` 前缀由 `init_logging()` 用裸 ANSI 单独着色，与 `colored()` 相互独立。

- `green`：命令，含待执行与执行成功（失败命令除外）
- `cyan`：正常展示的目录路径（错误信息中的路径除外）
- `red`：失败的命令，错误信息中被高亮的路径、命令、退出码
- `default`：工具自身元信息（版本 banner）、扫描结果数量等普通信息

`bold` 表示层级与强调：总览、阶段信息、结果汇总、需强调的值加粗；分项/条目（每个发现的目录、逐项目执行的路径与命令）不加粗。

## 参数

- 工具自身选项统一用 `--dca-` / `--docker-compose-all-` 前缀（例如 `--dca-scan-dir`、`--dca-verbose`、`--dca-cleanup`），与 `docker compose` 选项隔离；parser 设 `allow_abbrev=False`，不可用前缀缩写参数。
- 参数透传：除工具自身选项（`--dca-*/--docker-compose-all-*`、`-h/--help`、`-V/--version`）外，所有参数原样透传给 `docker compose`，因此 `docker compose` 的任意原生选项（`-f`、`--profile` 等）都可用。
- `parse_args()` 用 `parse_known_args` 在任意位置摘出工具自身选项，剩余 `unknown_args` 才透传给 `docker compose`。
- `-h/--help`、`-V/--version` 仅在整个 argv 恰为该参数时归工具自身，否则透传；例如 `up --help` 会透传为 `docker compose up --help`。
- 无 compose 命令时（argv 为空或仅工具选项），`parse_command_chain()` 返回的 `command_chain` 为空 list。此时 `main()` 扫描后，仅打印日志，跳过 `all_run_commands()`，但仍执行 cleanup 并打印 succeeded。
- 用 `;`/`&&`/`||` 串联多条命令（必须用引号、转义等方式防止被 shell 吃掉）。末尾的 `;` 视为命令终止符，允许并忽略；末尾的 `&&`/`||` 因缺少后继命令而报错。解析/校验失败故意不捕获异常，允许裸 traceback crash。采用 bash 短路语义，条件对每个项目独立求值，退出码取最后实际执行的命令，任一项目失败则整体退出 1。

## 版本与打包

- 版本号只在 `docker_compose_all/__init__.py` 的 `__version__` 中维护，`pyproject.toml` 通过 `dynamic` + `attr` 动态读取，无需在别处同步。
- 构建用 Makefile：`make build`（内部执行 `uvx --from build pyproject-build --installer uv`）；`make dev-install` 用于开发环境可编辑（editable）安装；`make install` 会先卸载再重装并 `pip show` 校验。
- 构建产物在 `dist/`，已被 `.gitignore` 忽略，不提交。

# 验证与测试

- 仓库没有 linter、formatter、CI 配置，不要臆造测试命令；改动后至少运行 `python3 -m docker_compose_all --version` 或 `--help` 做冒烟验证（如果本机未安装 Docker、Docker Compose，`check_system()` 会报错并退出 1）。
- `tests/` 为手动集成测试样例，无自动化 runner：`tests/success/` 全部项目有效（运行应退出 0），`tests/failure/` 混合有效与无效项目（应汇总报错并退出 1）。

# 其他

- `Readme.md` 的 Usage 段镜像 `--help` 帮助信息，改帮助信息后需同步到 `Readme.md`。
