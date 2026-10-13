# RemLocal QLoRA 准备方案 v1

- 核验日期：2026-10-11
- 目标：在 RTX 4060 Laptop 8GB 上准备 Qwen2.5-7B-Instruct 的低显存 QLoRA 试跑配置，不下载权重、不启动训练。

## 模型核验

`llama-cli` 从当前 GGUF 读取到以下元数据：

| 项目 | 结果 |
| --- | --- |
| 名称 | `Qwen2.5 7B Instruct` |
| 架构 | `qwen2` |
| 参数量 | 7.62B |
| 层数 | 28 |
| 原始上下文 | 32768 |
| 词表 | 152064 |
| 格式 | GGUF V3 |
| 量化 | Q4_K_M，4.91 BPW |
| 对话模板 | Qwen ChatML |
| llama.cpp | `b11093-fb34fc262` |

当前推理文件：

`D:\llama.cpp\models\Qwen2.5-7B-Instruct-Q4_K_M.gguf`

- 文件大小：`4683074240` 字节
- SHA-256：`65b8fcd92af6b4fefa935c625d1ac27ea29dcb6ee14589c55a8f115ceaaa1423`

GGUF 证明模型家族为 Qwen2.5-7B-Instruct，但没有记录转换时所用 Hugging Face 快照的提交 SHA。因此训练目标锁定为 `Qwen/Qwen2.5-7B-Instruct`。本项目已另外下载并固定官方 revision `a09a35458c702b33eeacc393d103063234e8bc28`；不能声称它就是原 GGUF 转换时使用的快照。

## 兼容结论

当前 GGUF 不能作为 QLoRA 训练输入。后续流程为：

`safetensors 基础模型 -> QLoRA 适配器 -> 合并权重 -> 转换 GGUF -> Q4_K_M 量化 -> llama.cpp 回归评测`

只要使用相同的 Qwen2.5-7B-Instruct 架构、分词器和 ChatML 模板，训练产物可以转换回 GGUF，并继续由当前 API、未来 EXE 启动器和 llama.cpp 使用。

## 8GB 试跑配置

配置文件：`configs/training/qwen2_5_7b_instruct_qlora_smoke_v1.json`

- 4-bit NF4 双重量化，计算类型 `bfloat16`；
- LoRA rank 16、alpha 32、dropout 0.05；
- batch size 1，梯度累积 4；
- 最大序列长度 1024，启用梯度检查点；
- 只计算 assistant 回复损失；
- 固定随机种子 42；
- 当前仅运行 2 个 step，用于检查加载、反向传播、验证和保存流程。

正式训练前必须扩大数据集并另建配置，不能把 smoke 配置的 `max_steps` 简单调大。

## 当前阻塞项

1. 独立训练环境和 Transformers、PEFT、TRL、bitsandbytes 尚未安装。
2. 当前只有 24 条训练样本，低于正式实验最低目标 300 条独立训练场景。
3. llama.cpp 当前占用约 6GB 显存；开始训练前必须停止推理服务，不能与 QLoRA 同时常驻。

当前状态是“架构兼容、基础权重已验证、试跑配置已确定，尚缺训练工具环境与正式数据规模”。
