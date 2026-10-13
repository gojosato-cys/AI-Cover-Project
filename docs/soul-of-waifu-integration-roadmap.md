# Soul-of-Waifu 融合路线

- 更新日期：2026-10-13
- 状态：里程碑 1A（纯文本流式与 GUI 接入）已完成；语音模型未启用

## 技术决策

Soul-of-Waifu 作为产品与交互层，RemLocal 继续作为人格模型、确定性安全路由、评测和微调层。两者通过 OpenAI 兼容 HTTP 接口连接，不把 Soul-of-Waifu 的 GPL-3.0 代码复制到当前仓库。

当前核验的 Soul-of-Waifu 源码位于 `D:\Soul-of-Waifu`，上游仓库为 `jofizcd/Soul-of-Waifu`，核验提交为 `747048b3b3ad7d321a667630018f7ffc04eb5f6d`。用于端到端测试的官方 Release v2.4.7 独立安装在 `D:\Soul-of-Waifu-app`。

```text
Soul-of-Waifu
  角色卡 / Lorebook / Soul Memory / 语音 / Live2D / RVC
                         |
                         | OpenAI-compatible API
                         v
RemLocal FastAPI  http://127.0.0.1:8000/v1
  安全路由 -> 人格规则 -> 任务规则 -> 完整上下文推理
                         |
                         v
llama.cpp         http://127.0.0.1:8080/v1
  Qwen2.5-7B / 后续的 Rem QLoRA GGUF
```

## 当前集成方式

1. 启动 `scripts/start_llama_server.ps1`。
2. 启动 `uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`。
3. 在 Soul-of-Waifu 选择 `Open AI` 会话方式。
4. Base URL 设为 `http://127.0.0.1:8000/v1`。
5. Model 设为 `RemLocal`，API Key 可留空或填写 `no-key-required`。

RemLocal 现在提供 `GET /v1/models` 和 `POST /v1/chat/completions`。Soul-of-Waifu 的角色卡、历史、Lorebook 和记忆会保留在完整 `messages` 中；RemLocal 的安全和稳定行为路由在调用模型前执行。

## 开发路线

### 里程碑 0：集成边界（已完成）

- 独立放置 GPL-3.0 上游仓库。
- 增加 OpenAI 兼容的模型列表和聊天接口。
- 保留 Soul 生成的多轮消息、人格与记忆上下文。
- 验证危机安全路由不会被 Soul 绕过。
- 提供 OpenAI 兼容 SSE 响应，保证 Soul 客户端兼容。

验收：单元测试通过，不改变原 `/api/chat` 行为。

### 里程碑 1A：真正流式与 GUI 接入（已完成）

- 从 llama.cpp 逐 token 转发 SSE，降低首字和 TTS 等待时间。
- 安装 Soul-of-Waifu v2.4.7，并通过官方原生 `OpenAIProvider` 接入 RemLocal。
- 验证纯文本、多轮历史、两份独立角色上下文、人格规则和危机安全路由。
- 验证 Soul GUI 可启动且进程稳定，不下载或加载完整语音模型。

2026-10-13 实测中，普通模型回复产生 12 个独立文本增量；多轮历史正确返回先前暗号，第二份角色上下文正确返回独立角色代号。GUI 窗口成功打开，Hugging Face 缓存启动前后均为 0 字节。SoX 缺失只影响后续音频能力，不影响本阶段文本链路。

验收：Soul 原生 provider 的 5 项端到端断言和 RemLocal 全量自动测试通过。

### 里程碑 1B：会话工程完善（下一阶段）

- 设定上下文长度、消息数和超时上限，并记录裁剪策略。
- 将客户端断开传递到 llama.cpp，支持取消正在生成的回复。
- 确定 Soul 工具调用的允许列表与审批边界。
- 将 Soul 原生 provider 冒烟测试整理为可重复运行的自动化检查。

验收：长对话裁剪、中断生成、超时和工具调用边界全部通过。

### 里程碑 2：雷姆角色资产统一

- 建立可版本化的 Soul 雷姆角色卡、系统提示和 Lorebook。
- 明确 RemLocal 安全策略为最高优先级，角色卡不复制或改写安全规则。
- 增加角色卡版本、记忆版本和模型版本的可观测信息。
- 使用现有 `rem_v2` 评测加入 Soul 调用路径的回归比较。

验收：Soul 和原网页对同一评测集的安全、身份和任务底线一致。

### 里程碑 3：本地语音与 RVC

- 先确定 ASR 和 TTS 的本地方案、许可证、显存和延迟预算。
- 接入有合法来源的声音资产，再配置 Soul 的 RVC 音色转换。
- 测量 ASR、LLM、TTS 和 RVC 分段延迟，避免同时抢占 8GB 显存。
- 保留文字降级路径，语音失败不影响聊天。

验收：完成一轮全本地语音对话，并有可重复的延迟和显存报告。

### 里程碑 4：雷姆人格 QLoRA

- 先实现 `max_steps=2` 训练入口、显存保护和检查点恢复。
- 将独立训练场景扩充至至少 300 条，保持评测集隔离并完成人工复核。
- 固定基础模型、数据指纹、随机种子和训练配置。
- 比较基础模型、提示词版本和 QLoRA 版本，不达验收门槛不替换。
- 通过后合并适配器，转换和量化 GGUF，由同一网关部署。

验收：人格人工评分有预先定义的提升，自动安全和任务评测无回归。

### 里程碑 5：AI Cover

- 将实时聊天 RVC 与歌曲翻唱流水线分开。
- 建立 UVR 人声/伴奏分离、去混响、RVC 转换、混音和缓存任务服务。
- 使用作业队列和独立进程，不阻塞实时聊天。
- 对输入音频、声音模型和生成物记录授权与来源。

验收：本地完成一个可追溯、可取消、不阻塞聊天的翻唱任务。

### 里程碑 6：打包与运维

- 提供统一启停器，检查 Soul、RemLocal 和 llama.cpp 的端口与健康状态。
- 模型、音频、缓存、日志和检查点继续固定在 D 盘。
- 锁定 Soul-of-Waifu 上游版本，升级前运行兼容和回归测试。
- 完成开源许可证清单、数据备份和故障恢复文档。

验收：新环境可根据锁定文档复现，且上游升级不会静默绕过安全或破坏人格。

## 暂不纳入首版的内容

- 不直接合并 Soul-of-Waifu 源码或将其改成当前仓库的子目录。
- 不在只有 24 条训练样本时启动正式人格训练。
- 不让 Soul 直连 llama.cpp，否则会绕过 RemLocal 安全和回归规则。
- 不把实时 RVC 等同于完整 AI Cover 流水线。
