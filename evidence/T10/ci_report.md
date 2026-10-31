# T10 CI 验证报告

| 项 | 内容 |
|---|---|
| 工作流文件 | `.github/workflows/arm64-ci.yml` |
| Runner | `ubuntu-24.04-arm`（QEMU ARM64 模拟） |
| 生成时间 | 2026-10-31 |

## 工作流结构

### Job 1: unit-tests
- 执行 T5（题库覆盖度）+ T6（备份恢复）+ T7（服务健壮性）
- 验证核心功能在 ARM64 环境下的正确性

### Job 2: end-to-end
- 自检（`_check_green_tools()`）通过
- 创建测试文件并上传到系统
- 启动服务并执行中文检索
- 执行备份导出
- 工件（artifacts）持久化上传到 GitHub Actions

## 验证结论

- **工作流文件存在且结构完整** ✓
- **尚未推送至 GitHub，未执行流水线**（需提交代码后触发 CI 运行）
- **预期结果**：若推送成功，CI 将自动在 QEMU ARM64 环境执行全部测试

## 真机差异风险声明（原文引用）

> QEMU ARM64 模拟与飞腾真机存在差异（尤其 onnxruntime 等原生库），甲方首次真机部署时如 RapidOCR 不可用，降级路径为 tesseract 引擎，该降级已内建于基线版本。

## 降级路径说明

| 引擎 | ARM64 可用性 | 降级条件 | 影响 |
|---|---|---|---|
| RapidOCR | 需 Python 3.8 wheel，3.13 不兼容 | 若 onnxruntime 在 QEMU 或真机上不可用 | 降级到 tesseract |
| tesseract | 绿色版随附，ARM64 可用 | 默认兜底引擎 | OCR 功能降级可用 |

## 后续行动

1. 推送代码至 GitHub 仓库后触发 CI
2. 获取 CI run 编号和 artifacts 链接
3. 更新本报告中"尚未执行"状态为实际运行结果
