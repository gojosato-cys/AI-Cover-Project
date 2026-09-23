# AI-Cover-Project / RemLocal

本仓库最初定位为基于 UVR 和 Applio 的 AI Cover Generator。当前工作区先完成了一个本地角色人格智能体的文字聊天 MVP，作为后续 AI 全栈项目的基础。

> 这是非官方同人学习项目，不代表原作品或角色官方设定。

## 当前功能

- 输入文字并获得本地模型人格回复
- `/api/health` 健康检查接口
- `/api/persona` 查看当前人格配置
- `/api/chat` 聊天接口（默认调用本机 llama.cpp，服务不可用时自动规则回退）
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

## 开发阶段

当前工作分支正在准备 `v0.2.0` 本地模型版本。后续计划包括：

1. 完善本地 llama.cpp 推理配置
2. 增加多轮上下文和长期记忆
3. 接入语音输入、语音合成与音频处理
4. 增加测试、日志、安全边界和部署配置

## 项目边界

本项目用于学习 AI 应用开发、后端接口、前端交互和本地模型集成。人格设定不声称是真实角色，也不替代医疗、法律或其他专业服务。
