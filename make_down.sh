#!/bin/bash

# 检查输入参数
if [ $# -ne 1 ]; then
    echo "错误：请提供包含测序文件的文件夹路径"
    echo "用法：$0 <输入文件夹路径>"
    exit 1
fi

input_dir="$1"

# 遍历输入文件夹中的R1文件
find "$input_dir" -name "*_1.fq.gz" | while read r1_path; do
    # 获取配对R2路径
    r2_path="${r1_path/_1.fq.gz/_2.fq.gz}"

    if [ ! -f "$r2_path" ]; then
        echo "警告：未找到配对文件 $r2_path"
        continue
    fi

    # 提取样本ID（假设文件名格式为XXXXX_1.fq.gz）
    sample_id=$(basename "$r1_path" "_1.fq.gz")

    # 生成任务脚本
    cat > "./script/${sample_id}_pipeline.sh" << EOF
#!/bin/bash

# 加载模块并激活上游环境
module load CentOS/7.9/Anaconda3/24.5.0

# 进入工作目录
cd /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/workflow/GutMicrobe-Virus-dev

# 激活下游环境
source activate /cpfs01/projects-HDD/cfff-47998b01bebd_HDD/rj_24212030018/miniconda3/envs/phadown

# 运行下游分析
python ./qua_indi.py -t 64 -o output -sample ${sample_id}
EOF

    # 添加执行权限
    chmod +x "./script/${sample_id}_pipeline.sh"
    echo "已生成样本 ${sample_id} 的流程脚本：${sample_id}_pipeline.sh"
done

echo "所有任务脚本已生成完成"
