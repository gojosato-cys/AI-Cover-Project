# AI-Cover-Project / RemLocal

本仓库最初定位为基于 UVR 和 Applio 的 AI Cover Generator。当前工作区先完成了一个本地角色人格智能体的文字聊天 MVP，作为后续 AI 全栈项目的基础。

> 这是非官方同人学习项目，不代表原作品或角色官方设定。

## 当前功能

- 输入文字并获得本地模型人格回复
- 使用可版本化的雷姆角色卡约束背景、语气、边界和任务行为
- 明确自伤意图由确定性危机安全路由处理，不依赖模型随机生成
- 明确询问雷姆身份或要求自我介绍时，稳定返回两句角色介绍
- 三天备考请求先返回可执行计划，再询问科目、范围和可用时间
- `/api/health` 健康检查接口
- `/api/persona` 查看当前人格配置
- `/api/chat` 聊天接口（默认调用本机 llama.cpp，服务不可用时自动规则回退）
- `/v1/models` 和 `/v1/chat/completions` OpenAI 兼容接口，用于接入 Soul-of-Waifu
- 预留后续接入 UVR、Applio 和语音能力的项目空间

## 目录

```text
backend/     FastAPI 后端
frontend/    无构建步骤的网页前端
```

## 本地运行

依赖会安装在 `D:\LeimuAi\.venv`，不会下载到其他盘。安装依赖后运行：

```powershell
cd D:\LeimuAi
.\.venv\Scripts\Activate.ps1
uvicorn backend.app.main:app --reload
```

然后用浏览器打开 `frontend/index.html`。

## 本地 llama.cpp

运行时文件和模型统一放在 `D:\llama.cpp`，不会下载到系统盘。准备好
`llama-server.exe` 和 GGUF 模型后，先启动服务：

```powershell
cd D:\LeimuAi
.\scripts\start_llama_server.ps1
```

服务地址为 `http://127.0.0.1:8080`，后端通过 `/v1/chat/completions` 调用。
没有启动模型服务时，`/api/chat` 会返回原有规则回复，并在 `source` 字段标记为回退。

## Soul-of-Waifu 融合

Soul-of-Waifu Release v2.4.7 独立安装在 `D:\Soul-of-Waifu-app`，通过 RemLocal 的 OpenAI 兼容网关调用本地模型。在 Soul 中选择 `Open AI`，将 Base URL 设为 `http://127.0.0.1:8000/v1`，Model 设为 `RemLocal`。这条路径会保留 Soul 的角色卡、Lorebook 和记忆上下文，同时保留 RemLocal 的确定性安全和任务路由。

当前已用 Soul 原生 `OpenAIProvider` 验证纯文本、多轮历史、两份独立角色上下文、人格规则、安全路由和逐 token SSE，并确认 GUI 可启动。此阶段未启用 TTS、Whisper 或 RVC 模型。

完整架构、版本边界、分阶段验收标准和后续路线见 `docs/soul-of-waifu-integration-roadmap.md`。

## 开发阶段

当前工作分支正在准备 `v0.2.0` 本地模型版本。后续计划包括：

1. 完善本地 llama.cpp 推理配置
2. 增加多轮上下文和长期记忆
3. 接入语音输入、语音合成与音频处理
4. 增加测试、日志、安全边界和部署配置

## 固定质量评测

启动后端后运行：

```powershell
cd D:\LeimuAi
.\.venv\Scripts\python.exe .\scripts\run_evaluation.py
```

评测会对 `tests/eval_cases/rem_v2.jsonl` 中的固定用例执行可复现的关键词、正则和结构检查，并把 JSON 报告写入 `data/eval-results/`。报告记录用例、评测器和关键服务代码的文件指纹、Git 版本及工作区状态、模型公开配置、分类汇总和每条规则的结果。

自动规则只负责检查明确、可机器判断的底线；语气、自然度和建议质量仍按报告中的 `manual_review` 人工复核。任一 HTTP 请求或整例自动规则未通过时，命令返回非零状态。

建立可比较的模型基线时，应使用相同模型文件、代码和用例，并将 `LLM_TEMPERATURE` 固定为 `0`；评测报告会记录实际温度，避免把随机采样差异误认为模型改进。

当前训练前质量基线见 `docs/persona-introduction-v1-evaluation-2026-10-11.md`：HTTP `12/12`、自动规则 `37/37`、自动整例 `12/12`。

## 微调数据准备

训练数据规范位于 `data/training/README.md`。本地数据按 `raw`、`processed` 和 `splits` 分层保存，实际 JSONL、校验报告及检查点默认不提交到 Git。

准备好本地 `train.jsonl`、`validation.jsonl` 和 `test.jsonl` 后运行：

```powershell
cd D:\LeimuAi
.\.venv\Scripts\python.exe .\scripts\validate_training_data.py
```

校验器会检查格式、来源状态、对话角色顺序、重复样本、跨集合对话组泄漏，以及与固定评测题的直接重复。只有校验通过并完成质量复核、标记为 `approved` 的样本才可进入训练。

首批 `rem-sft-v1-seed` 数据状态见 `docs/training-data-v1-2026-10-11.md`。该批数据用于验证数据与训练流水线，不足以单独支撑正式人格微调。

可训练基础权重已固定为 `Qwen/Qwen2.5-7B-Instruct` revision `a09a35458c702b33eeacc393d103063234e8bc28`，保存在 D 盘并完成分片校验。详情见 `docs/training-base-download-v1-2026-10-11.md`。

WSL2 QLoRA 工具链已安装在 `/home/gojosato/.venvs/remlocal-qlora`，完整版本锁定见 `configs/training/requirements-qlora-wsl.txt`，验证结果见 `docs/qlora-environment-v1-2026-10-11.md`。该环境已通过 CUDA、BF16 和 bitsandbytes NF4 轻量测试，但尚未加载 7B 模型或开始训练。

## 项目边界

本项目用于学习 AI 应用开发、后端接口、前端交互和本地模型集成。人格设定不声称是真实角色，也不替代医疗、法律或其他专业服务。
