# QLoRA 训练环境 v1 报告

日期：2026-10-11

## 结论

独立 QLoRA 训练环境已建立并通过轻量 GPU 验证，可进入训练脚本与两步 smoke test 的准备阶段。本次没有加载 7B 模型，也没有开始训练。

## 环境

- WSL：Ubuntu 24.04，数据位于 `D:\WSL\Ubuntu-24.04`
- Python：3.12.3
- 虚拟环境：`/home/gojosato/.venvs/remlocal-qlora`
- GPU：NVIDIA GeForce RTX 4060 Laptop GPU，8188 MiB
- Windows NVIDIA 驱动：581.15
- PyTorch：2.9.1+cu128
- CUDA runtime：12.8
- 主要训练库：Transformers 4.57.6、PEFT 0.18.1、TRL 0.24.0、bitsandbytes 0.48.2
- 完整锁定文件：`configs/training/requirements-qlora-wsl.txt`
- 机器环境清单：`configs/training/environment-qlora-wsl.json`

下载缓存固定在 `D:\LeimuAi\data\training\cache` 对应的 WSL 路径下，未向 C 盘写入模型或依赖缓存。虚拟环境位于 WSL ext4 文件系统，其 VHDX 实际存储在 D 盘。

## 验证结果

- `pip check`：通过，无依赖冲突
- torch、transformers、peft、trl、bitsandbytes、datasets、accelerate、safetensors：全部导入成功
- `torch.cuda.is_available()`：`true`
- GPU 名称：正确
- BF16 支持与 BF16 矩阵运算：通过
- bitsandbytes CUDA 编译后端：可用
- bitsandbytes NF4 量化和反量化：在 `cuda:0` 上通过

安装器首次批量解包时发生一次 Python 段错误。随后按 PyTorch、模型训练库、数据/TRL 三批重新安装，各批均成功，最终环境通过依赖与运行时检查。

## 边界与下一步

当前结论只证明训练工具链和 GPU 后端可用，不代表 8 GB 显存一定能以现有参数完整加载并训练 7B 模型。下一功能应实现训练入口与严格的显存保护，然后先运行 `max_steps=2` 的 QLoRA smoke test。真正加载训练模型前必须停止 llama.cpp，避免显存竞争。
