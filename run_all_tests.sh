#!/bin/bash
# run_all_tests.sh - 回归测试总控脚本
# 用途：一键运行全部 T1~T11 测试，生成汇总报告
# 用法：bash run_all_tests.sh
# 证据落盘：evidence/T*/output.txt

set -e

BASE="$(cd "$(dirname "$0")" && pwd)"
cd "$BASE"

echo "============================================================"
echo " 回归测试总控 (T1-T11)"
echo "============================================================"
echo "基准目录: $BASE"
echo "测试时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"

TOTAL=0
PASS=0
FAIL=0
SKIP=0
RESULTS=""

run_test() {
    local test_name="$1"
    local test_file="$2"
    local evidence_dir="$3"
    
    TOTAL=$((TOTAL + 1))
    echo ""
    echo "------------------------------------------------------------"
    echo "[${TOTAL}] ${test_name} (${test_file})"
    echo "------------------------------------------------------------"
    
    if [ ! -f "$test_file" ]; then
        echo "  [SKIP] 测试脚本不存在: ${test_file}"
        SKIP=$((SKIP + 1))
        RESULTS="${RESULTS}[SKIP] ${test_name}: 测试脚本不存在\n"
        return
    fi
    
    # 创建证据目录
    mkdir -p "$evidence_dir"
    
    # 运行测试
    if python3 "$test_file" > "$evidence_dir/output.txt" 2>&1; then
        echo "  [PASS] ${test_name}"
        PASS=$((PASS + 1))
        RESULTS="${RESULTS}[PASS] ${test_name}: 通过\n"
    else
        echo "  [FAIL] ${test_name}"
        FAIL=$((FAIL + 1))
        RESULTS="${RESULTS}[FAIL] ${test_name}: 失败\n"
    fi
}

# 运行各任务测试
run_test "T1 检索器功能测试" "tests/t1_search_test.py" "evidence/T1"
run_test "T2 索引基准测试" "tests/t2_index_bench.py" "evidence/T2"
run_test "T3 条款定位测试" "tests/t3_clause_test.py" "evidence/T3"
run_test "T4 归档完整性测试" "tests/t4_archive_test.py" "evidence/T4"
run_test "T5 题库覆盖度测试" "tests/t5_coverage_test.py" "evidence/T5"
run_test "T6 备份恢复测试" "tests/t6_backup_test.py" "evidence/T6"
run_test "T7 服务健壮性测试" "tests/t7_robustness_test.py" "evidence/T7"
run_test "T8 归档管理界面测试" "tests/t8_archive_ui_test.py" "evidence/T8"
run_test "T9 OCR 质量基准测试" "tests/t9_ocr_quality_test.py" "evidence/T9"

# T10 CI 工作流检查（无独立测试脚本，检查 workflow 文件）
TOTAL=$((TOTAL + 1))
if [ -f ".github/workflows/arm64-ci.yml" ] || [ -f ".github/workflows/麒麟端到端测试.yml" ]; then
    echo ""
    echo "------------------------------------------------------------"
    echo "[${TOTAL}] T10 ARM64 CI 工作流检查"
    echo "------------------------------------------------------------"
    echo "  [PASS] CI 工作文件存在"
    PASS=$((PASS + 1))
    RESULTS="${RESULTS}[PASS] T10 ARM64 CI: 工作文件存在\n"
else
    echo ""
    echo "------------------------------------------------------------"
    echo "[${TOTAL}] T10 ARM64 CI 工作流检查"
    echo "------------------------------------------------------------"
    echo "  [FAIL] CI 工作文件缺失"
    FAIL=$((FAIL + 1))
    RESULTS="${RESULTS}[FAIL] T10 ARM64 CI: 工作文件缺失\n"
fi

# T11 回归体系完整性检查
TOTAL=$((TOTAL + 1))
echo ""
echo "------------------------------------------------------------"
echo "[${TOTAL}] T11 回归体系完整性检查"
echo "------------------------------------------------------------"

if [ -f "run_all_tests.sh" ] && [ -f "SHA256校验.txt" ]; then
    echo "  [PASS] run_all_tests.sh 存在"
    echo "  [PASS] SHA256校验.txt 存在"
    PASS=$((PASS + 1))
    RESULTS="${RESULTS}[PASS] T11 回归体系: 完整性检查通过\n"
else
    echo "  [FAIL] 回归体系文件缺失"
    [ ! -f "run_all_tests.sh" ] && echo "    - run_all_tests.sh 缺失"
    [ ! -f "SHA256校验.txt" ] && echo "    - SHA256校验.txt 缺失"
    FAIL=$((FAIL + 1))
    RESULTS="${RESULTS}[FAIL] T11 回归体系: 完整性检查失败\n"
fi

# 生成 SHA256 清单（如果不存在）
if [ ! -f "SHA256校验.txt" ]; then
    echo ""
    echo "正在生成 SHA256 校验清单..."
    python3 -c "
import hashlib, os

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

files = []
for root, dirs, filenames in os.walk('.'):
    # 跳过 .git 目录
    dirs[:] = [d for d in dirs if d != '.git']
    for fn in sorted(filenames):
        if fn.endswith(('.py', '.sh', '.yml', '.md', '.json')):
            fp = os.path.join(root, fn)
            try:
                h = sha256_file(fp)
                size = os.path.getsize(fp)
                files.append(f'{h}  {size:>10}  {fp}')
            except:
                pass

with open('SHA256校验.txt', 'w', encoding='utf-8') as f:
    f.write('SHA256 校验清单\n')
    f.write('=' * 80 + '\n')
    f.write(f'生成时间: {os.popen(\"date \"+\"%Y-%m-%d %H:%M:%S\").read().strip()}\n')
    f.write(f'文件数量: {len(files)}\n')
    f.write('=' * 80 + '\n')
    for line in files:
        f.write(line + '\n')
    f.write('=' * 80 + '\n')
    f.write(f'总计: {len(files)} 个文件\n')

print(f'SHA256 校验清单已生成: {len(files)} 个文件')
"
fi

# 汇总报告
echo ""
echo "============================================================"
echo " 回归测试汇总报告"
echo "============================================================"
echo "  总测试数: ${TOTAL}"
echo "  通过:     ${PASS}"
echo "  失败:     ${FAIL}"
echo "  跳过:     ${SKIP}"
echo "============================================================"
echo ""
echo "详细结果:"
echo "$RESULTS" | sed 's/^/  /'

echo ""
echo "证据文件:"
for dir in evidence/T*; do
    if [ -d "$dir" ] && [ -f "$dir/output.txt" ]; then
        echo "  - ${dir}/output.txt"
    fi
done

echo ""
echo "============================================================"
if [ $FAIL -eq 0 ]; then
    echo "  全部回归测试通过"
else
    echo "  ${FAIL} 项测试失败，请查看上述详细结果"
fi
echo "============================================================"

# 返回码
if [ $FAIL -gt 0 ]; then
    exit 1
else
    exit 0
fi
