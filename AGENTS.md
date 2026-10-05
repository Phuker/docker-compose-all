# 项目概览

docker-compose-all 是一个 Python CLI 工具，递归扫描目录（默认 `.`）下的所有 Docker Compose 项目，并在每个项目目录中批量执行 `docker compose` 命令。

包结构单一：

- `docker_compose_all/docker_compose_all.py`：全部核心逻辑与 CLI 入口
- `docker_compose_all/__init__.py`：唯一版本来源 `__version__`
- `docker_compose_all/__main__.py`：`python -m docker_compose_all` 入口

# 设计细节

- 调用的是 `docker compose`（`docker` 子命令），不是旧版 `docker-compose`。
- 扫描目录来自 `--dca-scan-dir`（默认 `.`）；`scan_dirs()` 会 `os.walk(..., followlinks=True)`，软链接可能造成重复扫描；项目识别依据文件名：`compose.yaml` / `compose.yml` / `docker-compose.yaml` / `docker-compose.yml`。
- `shell_args`、`error_info_list` 为模块级全局可变状态。
- 非 root 只告警不退出（`logger.warning('Not running as root')`）。
- 将各项目的 `dir_path` 作为 `cwd` 参数传入 `subprocess.check_call()`，不改变当前进程 cwd，无 cwd 副作用。
- `cleanup()` 由 `--dca-cleanup` 触发，对应 `COMMANDS_CLEANUP` / `COMMAND_CLEANUP_*`，依次执行 `docker network/image/builder prune -f`，仅在全部项目命令成功（`error_info_list` 为空）时执行；存在错误时跳过并告警。清理命令用 `subprocess.call` 执行，返回码被忽略。

## 日志颜色与字重

使用 `colored()` 改变日志正文的颜色、字重，设计要体现出主/次、总/分，内部统一，符合 CLI 软件惯例。仅局部突出显示日志正文中的值，其余文本保持普通样式。

颜色表达语义类别：`green` 表示命令（待执行、执行成功，失败命令除外），`cyan` 表示路径（错误信息除外），`red` 表示失败的命令、路径、错误信息，`default` 表示工具自身元信息（版本 banner）等普通信息

字重表达层级与强调：`bold` 用于总览、阶段性信息、结果汇总、需要强调的值，分项/条目级信息（每个发现的目录、逐项目执行的路径与命令）不加粗

## 参数

- 工具自身选项统一用 `--dca-` / `--docker-compose-all-` 前缀（例如 `--dca-scan-dir`、`--dca-verbose`、`--dca-cleanup`），与 `docker compose` 选项隔离；parser 设 `allow_abbrev=False`，不可用前缀缩写参数。
- 参数透传：除工具自身选项（`--dca-*/--docker-compose-all-*`、`-h/--help`、`-V/--version`）外，所有参数原样透传给 `docker compose`，因此 `docker compose` 的任意原生选项（`-f`、`--profile` 等）都可用。
- `parse_args()` 用 `parse_known_args` 在任意位置摘出工具自身选项，剩余 `unknown_args` 才透传给 `docker compose`
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

- `Readme.md` 的用法输出可能滞后于代码，以 `--help` 实际输出为准。
