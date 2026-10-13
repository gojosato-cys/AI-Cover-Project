# RemLocal / Soul-of-Waifu 项目交接

- 交接日期：2026-10-13
- 当前分支：`feature/local-llm`
- 已完成功能提交：`251a050 feat: 融合 Soul-of-Waifu 文本流式链路`
- 远端仓库：`https://github.com/gojosato-cys/AI-Cover-Project.git`
- 当前阶段：里程碑 1A 已完成，准备进入里程碑 1B

## 一句话结论

项目已经形成一条可用的本地纯文本链路：Soul-of-Waifu 负责 GUI、角色上下文和会话体验，RemLocal 负责最高优先级的人格、任务和安全路由，llama.cpp 负责 Qwen2.5-7B 本地推理；多轮、双角色上下文和真正逐 token 流式均已验证。正式人格微调和完整语音链路尚未开始。

## 架构与边界

```text
Soul-of-Waifu v2.4.7
  GUI / 角色卡 / Lorebook / 会话历史
                   |
                   | OpenAI-compatible HTTP + SSE
                   v
RemLocal FastAPI   http://127.0.0.1:8000/v1
  安全路由 -> 人格规则 -> 任务规则 -> 上下文适配
                   |
                   v
llama.cpp          http://127.0.0.1:8080/v1
  Qwen2.5-7B-Instruct Q4_K_M
```

边界约定：

- Soul-of-Waifu 保持在独立目录，通过 HTTP 集成，不复制其 GPL-3.0 源码到本仓库。
- Soul 不应直连 llama.cpp，否则会绕过 RemLocal 的确定性安全和任务路由。
- 模型、训练数据、缓存、日志和检查点放在 D 盘，不提交 Git。
- 当前阶段只验收文本链路，不同时加载完整 TTS、Whisper 或 RVC 模型。

## 关键目录与版本

| 项目 | 位置或版本 |
| --- | --- |
| RemLocal 仓库 | `D:\LeimuAi` |
| Soul 官方 Release | `D:\Soul-of-Waifu-app`，v2.4.7 |
| Soul 上游源码核验目录 | `D:\Soul-of-Waifu` |
| Soul 上游核验提交 | `747048b3b3ad7d321a667630018f7ffc04eb5f6d` |
| Soul 下载与缓存 | `D:\Soul-of-Waifu-runtime` |
| llama.cpp | `D:\llama.cpp\b11093\llama-server.exe` |
| 当前推理模型 | `D:\llama.cpp\models\Qwen2.5-7B-Instruct-Q4_K_M.gguf` |
| 可训练基础权重 | `D:\LeimuAi\data\training\models\Qwen2.5-7B-Instruct` |
| QLoRA WSL 环境 | `/home/gojosato/.venvs/remlocal-qlora` |

推理模型和可训练权重的 SHA-256、大小、固定 revision 见 `data/training/manifests/model_v1.json`。

## 已完成内容

### 1. 本地推理与兼容网关

- `/api/health`、`/api/persona`、`/api/chat` 可供原有前端使用。
- `/v1/models`、`/v1/chat/completions` 可供 Soul 的标准 OpenAI 客户端使用。
- Soul 发送的 system、user、assistant 历史消息会完整保留。
- RemLocal 系统策略始终放在 Soul 角色上下文之前。
- llama.cpp 的 SSE `delta.content` 已逐块解析并立即透传，不再等待完整回复。
- 模型不可用时仍保留规则回退；可通过环境变量关闭回退以暴露故障。

主要代码：

- `backend/app/main.py`：API、OpenAI 兼容响应和 SSE 输出。
- `backend/app/llm_service.py`：上下文合并、llama.cpp 调用和流解析。

### 2. 人格、任务和安全路由

- `rem-persona-v1`：版本化雷姆人格、语气、边界和任务原则。
- `persona-introduction-v1`：身份询问走稳定的两句自我介绍。
- `three-day-study-plan-v1`：三天备考请求先给方案，再询问必要信息。
- `self-harm-crisis-v1`：直接自伤意图绕过模型，优先给现实安全步骤。

主要代码：

- `backend/app/persona.py`
- `backend/app/planning.py`
- `backend/app/safety.py`

### 3. Soul-of-Waifu 接入

Soul 当前配置：

- Conversation Method：`Open AI`
- Base URL：`http://127.0.0.1:8000/v1`
- Model：`RemLocal`
- API Key：可留空，provider 会使用 `no-key-required`
- Soul Memory：关闭
- Auto Summary：关闭

已使用 Soul 自带环境中的原生 `AIFactory/OpenAIProvider` 验证：

- 多轮历史能返回上一轮暗号。
- 两份 system 上下文能保持不同角色代号。
- 人格规则和危机安全路由可从 Soul 调用路径触发。
- 普通模型回复产生多个独立增量块，确认是真流式。
- GUI 能打开并保持响应；测试前后 Hugging Face 缓存均为 0 字节。

注意：仓库内 `tests/test_soul_integration.py` 自动验证协议、上下文、安全路由和分块逻辑；Soul 官方安装环境的原生 provider/GUI 检查目前仍是人工冒烟测试，尚未脚本化。

### 4. 质量评测

- `tests/eval_cases/rem_v2.jsonl`：12 条固定用例、37 条透明规则。
- `scripts/run_evaluation.py`：记录用例、评测器、服务代码指纹、Git 状态和模型公开配置。
- 评测报告写入 `data/eval-results/`，该目录已被 Git 忽略。
- 2026-10-13 在 `LLM_TEMPERATURE=0` 下的结果：HTTP `12/12`、规则 `37/37`、整例 `12/12`。
- `LLM_TEMPERATURE=0.7` 曾出现 `34/37`、`9/12`，说明对比基线必须固定温度 0；日常聊天仍可使用默认 0.7。

自动规则通过不等于最终质量验收，语气、自然度和建议质量仍需人工复核。

### 5. 微调准备

- 已建立训练数据 Schema、来源清单、去重和跨集合泄漏校验。
- 已固定 `Qwen/Qwen2.5-7B-Instruct` revision：`a09a35458c702b33eeacc393d103063234e8bc28`。
- 可训练 safetensors 权重已下载到 D 盘并完成分片校验。
- WSL2 QLoRA 环境已通过 CUDA、BF16 和 bitsandbytes NF4 轻量检查。
- 已有 `max_steps=2` 的低显存试跑配置，但没有训练入口脚本，尚未加载 7B 基础模型或开始训练。
- 当前只有约 24 条种子样本，不足以支撑正式人格微调。

## 已通过的验证

在功能提交 `251a050` 上：

- 标准库单元测试：`53/53` 通过。
- Python 模块编译检查通过。
- Soul 原生 provider 五项端到端断言通过。
- Soul GUI 启动成功，窗口响应正常。
- 固定温度 0 在线评测：`12/12` 用例、`37/37` 规则通过。
- Git 敏感信息扫描未发现高置信度凭据。
- 待提交文件中没有超过 1 MiB 的文件，模型与缓存均被忽略。

当前交接时服务未运行，`8000`、`8080` 均未监听，Soul GUI 也未启动。这是运行状态，不是测试失败。

## 启动与复验

### 1. 启动 llama.cpp

```powershell
cd D:\LeimuAi
.\scripts\start_llama_server.ps1
Invoke-RestMethod http://127.0.0.1:8080/health
```

### 2. 启动 RemLocal

日常聊天：

```powershell
cd D:\LeimuAi
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

固定质量评测需要在启动前设置温度 0：

```powershell
cd D:\LeimuAi
$env:LLM_TEMPERATURE = '0'
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

### 3. 运行自动测试

项目虚拟环境没有安装 pytest，使用标准库 unittest：

```powershell
cd D:\LeimuAi
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

### 4. 运行固定评测

```powershell
cd D:\LeimuAi
.\.venv\Scripts\python.exe .\scripts\run_evaluation.py --base-url http://127.0.0.1:8000
```

### 5. 启动 Soul GUI

确认 8000 和 8080 健康后运行：

```powershell
cd D:\Soul-of-Waifu-app
.\app\data\envs\sow\python.exe .\main.py
```

不要在本阶段打开 TTS、Whisper、RVC 或自动记忆下载项。

## 已知限制与非阻塞警告

- Soul 环境未安装 SoX；这只影响音频能力，不影响文本聊天。
- Soul 的 GitHub 更新检查曾返回 403，不影响本地运行。
- Soul 环境存在若干上游语音/RVC 依赖告警：`fairseq/cython`、`ffmpeg-python/future`、spaCy 模型版本、`rvc-python/numpy`。不要为了文本阶段盲目降级 numpy。
- 当前没有上下文裁剪策略，长会话可能超过 llama.cpp 的 4096 context。
- 客户端断开还不会可靠取消上游 llama.cpp 生成。
- 工具调用没有明确白名单和审批边界。
- Soul 原生 provider 冒烟测试尚未成为仓库内可重复脚本。
- Soul Memory 和 Auto Summary 暂时关闭，长期记忆尚未验收。
- 当前模型仍是通用 Qwen2.5-7B-Instruct，不是已完成微调的 Rem 模型。

## 下一步执行顺序

### P0：完成会话工程里程碑 1B

1. 为 system 和历史消息设定 token/消息数上限，并实现可测试的裁剪策略；必须保留 RemLocal 安全提示和最近对话。
2. 将 HTTP 客户端断开传递到上游流，支持取消生成并确认连接、线程和响应对象被释放。
3. 明确超时、llama.cpp 中断和半途中断时的 SSE 错误/结束语义。
4. 定义 Soul 工具调用白名单；默认拒绝文件、Shell、网络和外部副作用工具。
5. 把 Soul 原生 provider 五项冒烟测试整理成脚本，输出明确的通过/失败结果，不依赖语音模型。

验收：长对话裁剪、中断生成、超时、规则优先级和工具边界均有自动测试；原 `53` 项及 `rem_v2` 基线无回归。

### P1：统一雷姆角色资产

1. 建立版本化 Soul 角色卡、Lorebook 和示例对话，记录版本与来源。
2. 避免在 Soul 角色卡中复制安全策略；RemLocal 安全层保持最高优先级。
3. 在 `/api/health` 或响应元数据中公开角色卡、记忆和模型版本。
4. 让 `rem_v2` 同时跑原 `/api/chat` 与 Soul/OpenAI 路径，比较人格、安全和任务底线。

验收：两个入口的底线规则一致，多角色切换不会串人格或记忆。

### P2：决定是否进行 QLoRA

1. 先实现 `max_steps=2` 训练入口、显存保护、日志和检查点恢复，并仅做流水线试跑。
2. 将独立、合规、人工复核的训练场景扩充到至少 300 条。
3. 保证固定评测集不进入训练数据，按 `group_id` 防止跨集合泄漏。
4. 预先定义人格人工评分与安全无回归门槛，再比较基础模型、提示词版本和 QLoRA。
5. 只有达到门槛才合并适配器、转换 GGUF 并替换部署模型。

### P3：最后接入语音与 AI Cover

1. 先确定 ASR、TTS、RVC 的许可证、显存和延迟预算。
2. 逐个加载组件并测量显存，避免与 7B 模型同时挤占 8GB 显存。
3. 保留文本降级路径，语音失败不能阻塞聊天。
4. AI Cover 使用独立作业队列，不与实时聊天 RVC 混为一条同步流水线。

## 接手人第一天建议

1. 阅读 `README.md` 和 `docs/soul-of-waifu-integration-roadmap.md`。
2. 确认分支为 `feature/local-llm`，执行 `git pull --ff-only`。
3. 启动 8080、8000，运行 53 项单元测试和温度 0 的 `rem_v2` 评测。
4. 启动 Soul GUI，只做一次纯文本多轮与安全路由冒烟测试。
5. 从 P0 的“上下文裁剪策略”开始实现，完成并验收后再进入取消生成。

## 关键文档

- 运行说明：`README.md`
- 总体路线：`docs/soul-of-waifu-integration-roadmap.md`
- 当前评测基线：`docs/persona-introduction-v1-evaluation-2026-10-11.md`
- 训练数据规范：`data/training/README.md`
- 基础权重记录：`docs/training-base-download-v1-2026-10-11.md`
- QLoRA 环境：`docs/qlora-environment-v1-2026-10-11.md`
- QLoRA 准备方案：`docs/qlora-preparation-v1-2026-10-11.md`

## 禁止事项

- 不要强推 `feature/local-llm`。
- 不要提交 GGUF、safetensors、训练拆分、缓存、日志或本地凭据。
- 不要让 Soul 绕过 RemLocal 直连 llama.cpp。
- 不要在文本链路未保持稳定时同时加载完整语音模型。
- 不要用 0.7 温度的随机结果与温度 0 的固定基线直接比较。
- 不要在 24 条种子样本上宣称完成正式人格微调。
