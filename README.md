# RemLocal

本地部署的角色人格语音智能体练习项目。当前阶段完成了“文字聊天 MVP”骨架：网页聊天界面、FastAPI 接口和可替换的角色人格回复服务。

> 这是非官方同人学习项目，不代表原作品或角色官方设定。

## 当前功能

- 输入文字并获得演示人格回复
- `/api/health` 健康检查接口
- `/api/persona` 查看当前人格配置
- `/api/chat` 聊天接口（暂时使用规则演示回复，下一阶段替换为本地大语言模型）

## 目录

```text
backend/     FastAPI 后端
frontend/    无构建步骤的网页前端
```

## 后续运行方式

依赖会安装在 `D:\LeimuAi\.venv`，不会下载到其他盘。安装依赖后运行：

```powershell
cd D:\LeimuAi
.\.venv\Scripts\Activate.ps1
uvicorn backend.app.main:app --reload
```

然后用浏览器打开 `frontend/index.html`。
