# RemLocal 微调数据规范 v1

当前阶段只建立数据约定和校验基线，不下载基础模型，也不启动训练。

## 目录

| 路径 | 用途 | Git 策略 |
| --- | --- | --- |
| `raw/` | 原始资料或人工草稿，只读保存 | 忽略内容 |
| `processed/` | 清洗、规范化和去重后的中间数据 | 忽略内容 |
| `splits/` | 最终 `train.jsonl`、`validation.jsonl`、`test.jsonl` | 忽略 JSONL |
| `manifests/sources.jsonl` | 来源、创建方式和使用范围记录 | 跟踪 |
| `schemas/` | 数据与来源清单 JSON Schema | 跟踪 |
| `reports/` | 校验和统计报告 | 忽略内容 |
| `checkpoints/` | 后续训练检查点 | 忽略内容 |
| `models/` | 后续下载的可训练 `safetensors` 基础权重 | 忽略内容 |
| `cache/` | 训练工具与模型缓存 | 忽略内容 |

所有实际数据、模型、日志和检查点都保存在 D 盘，不复制到系统盘。

## 样本格式

每行是一个独立 JSON 对象，必须符合 `schemas/rem_sft_v1.schema.json`。最小示例：

```json
{"schema_version":"rem-sft-v1","id":"rem-example-000001","source_id":"rem-original-v1","group_id":"rem-scene-000001","split":"train","category":"persona","language":"zh-CN","messages":[{"role":"user","content":"今天有些累。"},{"role":"assistant","content":"辛苦了。先休息几分钟，再告诉雷姆最让你疲惫的是哪一部分吧。"}],"quality":{"status":"approved","reviewer":"project-owner","notes":"人工原创示例"}}
```

`messages` 默认使用用户与助手交替的对话。可以在第一条放一个 `system` 消息，但普通人格样本不重复嵌入整张角色卡；训练工具应统一注入版本化系统提示词。

## 隔离规则

- `id` 在全部集合中唯一。
- 同一原始对话、同一场景的改写和近似改写必须使用相同 `group_id`。
- 一个 `group_id` 只能出现在一个集合，必须先按组切分，再进行改写或扩充。
- 规范化后完全相同的对话不能重复出现，包括同一集合内重复。
- 固定评测题不能进入训练、验证或微调测试数据；评测集始终独立保存于 `tests/eval_cases/`。
- `test.jsonl` 只用于最终比较，不参与参数选择；`validation.jsonl` 可用于早停和选择检查点。
- 所有进入最终集合的样本必须经过独立质量复核，记录真实复核者，并标记为 `quality.status = approved`。模型辅助生成的样本必须在来源清单中明确标记为 `model_assisted`。

数据量较少时不要强行追求固定比例。先保证每个关键类别在验证集和测试集中都有独立场景；数据规模足够后再采用约 80/10/10 的组级切分。

## 工作流

1. 在 `manifests/sources.jsonl` 登记来源，并分配稳定的 `source_id`。
2. 把原始内容放进 `raw/<source_id>/`，不直接修改原件。
3. 清理个人信息、占位文本和低质量内容，结果写入 `processed/`。
4. 按 `group_id` 切分为三个集合，再做集合内改写。
5. 进行独立质量复核，只有 `approved` 样本写入 `splits/*.jsonl`。
6. 运行 `scripts/validate_training_data.py`；校验通过后才能启动训练实验。

基础模型和试跑参数分别记录在 `manifests/model_v1.json` 与 `configs/training/qwen2_5_7b_instruct_qlora_smoke_v1.json`。配置中的 `base_model_revision` 在下载前必须替换为不可变提交 SHA。
