# RemLocal 可训练基础权重下载 v1

- 下载日期：2026-10-11
- 仓库：`Qwen/Qwen2.5-7B-Instruct`
- 固定 revision：`a09a35458c702b33eeacc393d103063234e8bc28`
- 本地目录：`D:\LeimuAi\data\training\models\Qwen2.5-7B-Instruct`

## 结果

- 下载文件：13 个；
- 文件总量：15,242,805,751 字节；
- 四个权重分片：15,231,271,888 字节；
- 索引声明张量总量：15,231,233,024 字节；
- D 盘下载后剩余空间：约 151.0 GB；
- 下载缓存和模型文件均位于 D 盘。

`config.json` 确认架构为 `Qwen2ForCausalLM`，模型类型 `qwen2`，28 层、隐藏维度 3584、28 个注意力头、4 个 KV 头、词表 152064、上下文 32768，原始权重类型为 `bfloat16`。这些参数与当前 GGUF 元数据一致。

## 权重校验

| 文件 | 字节 | SHA-256 |
| --- | ---: | --- |
| `model-00001-of-00004.safetensors` | 3,945,441,440 | `a1333e6293854747c481288ea83b348226af178dd565c49b6f9495ba1966aba7` |
| `model-00002-of-00004.safetensors` | 3,864,726,352 | `f5d25a2772cb825164a2a2c0fb6d51a87e282abf21e4dd75bc5cfb3cd0ea6185` |
| `model-00003-of-00004.safetensors` | 3,864,726,424 | `8efdec4c1bc12317ae1a38dc42b595ce777738a64deea3fcb8a0a91381bcdfd5` |
| `model-00004-of-00004.safetensors` | 3,556,377,672 | `1a72d403cdf0c1ec3cb7f289f17b394a01e64394c2e9b3c0f94dbce3faf879bd` |

四个本地 SHA-256 均与该 revision 的官方 LFS SHA-256 完全一致。`model.safetensors.index.json` 引用的四个分片全部存在，13 个本地文件的完整指纹已写入 `data/training/manifests/model_v1.json`。

## 状态

基础模型下载与完整性验证已经完成。尚未安装 QLoRA 训练工具，也没有启动训练；当前 llama.cpp 推理服务和 FastAPI 保持运行。
