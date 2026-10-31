# T9 OCR 质量基准报告

| 项 | 内容 |
|---|---|
| 测试时间 | 2026-10-31 |
| 测试环境 | Windows 11, Python 3.13 |
| 归档目录 | `归档/`（38 个文件） |

## 测试执行结果

### T9-1：tesseract 引擎可用性检测
- **状态**：FAIL
- **原因**：`tesseract工具/usr/bin/tesseract` 为 Linux ARM64 绿色版二进制，Windows 环境下执行返回 `[WinError 193] %1 不是有效的 Win32 应用程序`
- **结论**：Windows 环境不可用，需部署至 Linux/ARM64 环境

### T9-2：RapidOCR 引擎可用性检测
- **状态**：FAIL
- **原因**：RapidOCR 离线 wheel 包（`RapidOCR离线包/rapidocr_wheels/`）仅支持 Python 3.8，当前环境 Python 3.13 不兼容
- **结论**：需编译 Python 3.13 兼容 wheel 后方可使用

### T9-3：中文 OCR 数据检测
- **状态**：PASS
- **chi_sim.traineddata**：存在于 `tesseract工具/usr/share/tesseract/tessdata/chi_sim.traineddata`，文件大小 2411 KB ✓

### T9-4：归档目录真实扫描件扫描
- **状态**：FAIL
- **结果**：找到 0 份真实扫描件（要求 ≥10）
- **原因分析**：`归档/劳动合同法.pdf`、`归档/劳动法.pdf`、`归档/社会保险法.pdf` 三个 PDF 文件实际为 UTF-8 文本文件（文件头为 `\xe4\xb8\xad\xe5\x8d\x8e\xe4\xba` 即"中华"二字），非真实 PDF 扫描件

### T9-5：OCR 质量测试（≥10 份扫描件）
- **状态**：FAIL
- **原因**：当前 0 份真实扫描件，无法进行质量测试
- **无法提供的数据**：逐样本识别字符数、抽检首 200 字错字数、准确率、错字漏检专项结论

### T9-6：形近字容错表（OCR 容错检索）
- **状态**：PASS
- **形近字表**：`形近字表.json`，文件大小 1884 字 ✓
- **作用**：OCR 识别错字兜底检索，通过形近字映射提升召回率

### T9-7：poppler PDF 处理工具
- **状态**：FAIL
- **原因**：`poppler工具/usr/bin/pdftotext` 为 Linux ARM64 绿色版二进制，Windows 环境下执行返回 `[WinError 193] %1 不是有效的 Win32 应用程序`
- **结论**：Windows 环境不可用，需部署至 Linux/ARM64 环境

## 综合结论

| 测试项 | 状态 | 通过率 |
|---|---|---|
| T9-1 tesseract 引擎 | FAIL | |
| T9-2 RapidOCR 引擎 | FAIL | |
| T9-3 chi_sim 数据 | PASS | |
| T9-4 真实扫描件扫描 | FAIL | |
| T9-5 OCR 质量测试 | FAIL | |
| T9-6 形近字容错表 | PASS | |
| T9-7 poppler 工具 | FAIL | |
| **总计** | **2/7 通过** | **28.6%** |

## 根因分析

1. **环境限制**：开发环境为 Windows，tesseract/pdftotext 均为 Linux ARM64 绿色版二进制，Windows 无法执行
2. **Python 版本不兼容**：RapidOCR wheel 仅支持 Python 3.8，当前环境 Python 3.13
3. **PDF 文件非真实扫描件**：归档中 3 个 `.pdf` 文件为 UTF-8 文本文件（伪造扩展名），无真实扫描件样本

## 后续修复路径

| 步骤 | 操作 | 预期结果 |
|---|---|---|
| 1 | 部署至 Linux/ARM64 环境（飞腾真机或 QEMU ARM64） | tesseract/pdftotext 可执行 |
| 2 | 补充 ≥10 份真实扫描版法规 PDF 至 `归档/` 目录 | T9-4/T9-5 可执行 |
| 3 | 编译 RapidOCR Python 3.13 兼容 wheel（按 `03可选升级.txt`） | RapidOCR 可初始化 |
| 4 | 重跑 T9 全部测试 | 产出完整 OCR 基线报告 |

## 兜底机制

- **形近字容错表**（1884 字）已就绪，可作为 OCR 错字兜底检索
- **tesseract 引擎**绿色版已随附（ARM64），部署后可用
- **降级路径**：RapidOCR 不可用时自动降级到 tesseract，不影响基本 OCR 功能
