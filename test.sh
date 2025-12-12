#!/bin/bash
# 测试脚本

# === 单样本测试 ===

# 测试1: 从测序文件开始
echo "测试1: 从测序文件开始"
python run_upstream.py \
    /home/raojun/testdata/myR1.fq.gz \
    /home/raojun/testdata/myR2.fq.gz \
    --start-from reads \
    --host hg38 \
    -o results \
    -t 16 \
    --config config/config.yaml \
    --log-level INFO

# 测试2: 从contigs开始
echo "测试2: 从contigs文件开始"
python run_upstream.py \
    /home/raojun/testdata/sample.contigs.fa \
    --start-from contigs \
    -o results \
    -t 16 \
    --config config/config.yaml \
    --log-level INFO


# === 批量分析测试 ===

# 测试3: 批量reads分析
echo "测试3: 批量测序文件分析"
python make.py /home/raojun/testdata/reads/ \
    --mode reads \
    --host hg38 \
    -t 16 \
    -o batch_results

# 测试4: 批量contigs分析
echo "测试4: 批量contigs分析"
python make.py /home/raojun/testdata/contigs/ \
    --mode contigs \
    -t 16 \
    -o batch_results


# === 病毒库构建测试 ===

# 测试5: 从上游结果构建病毒库
echo "测试5: 从上游结果构建病毒库"
python viruslib_pipeline.py \
    --upstream-result results \
    -t 16 \
    -o viruslib_result \
    --config config/config.yaml

# 测试6: 从指定contigs目录构建病毒库
echo "测试6: 从指定contigs目录构建病毒库"
python viruslib_pipeline.py \
    -i /home/raojun/testdata/final_contigs/ \
    -t 16 \
    -o viruslib_result_custom \
    --config config/config.yaml

# 测试7: 检查病毒库结果
echo "测试7: 检查病毒库结果"
if [ -f "viruslib_result/2.vclust_dedup/viruslib_nr.fa" ]; then
    echo "✓ 病毒库生成成功"
    echo "统计信息:"
    echo "  原始序列数: $(grep -c "^>" viruslib_result/1.merge_contigs/all_contigs.fa || echo 0)"
    echo "  去冗余后: $(grep -c "^>" viruslib_result/2.vclust_dedup/viruslib_nr.fa || echo 0)"
    echo "  前5个vOTU:"
    grep "^>" viruslib_result/2.vclust_dedup/viruslib_nr.fa | head -5
else
    echo "✗ 病毒库生成失败"
fi

echo ""
echo "=== 所有测试完成 ==="