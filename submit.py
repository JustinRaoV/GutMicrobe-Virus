import sys
from pathlib import Path


def generate_submit_script(script_dir):
    # 收集所有.sh文件的绝对路径
    commands = []
    for sh_file in script_dir.glob("*.sh"):
        abs_path = sh_file.resolve()
        commands.append(f"sbatch -n 32 --mem=200G {abs_path}")

    # 写入submit.txt
    with open("submit.txt", "w") as f:
        f.write("\n".join(commands))

    print(f"成功生成 {len(commands)} 条提交命令")
    print("结果文件已保存为：submit.txt")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("错误：请指定包含任务脚本的文件夹路径")
        print("用法：python generate_submit.py <script文件夹路径>")
        sys.exit(1)

    script_dir = Path(sys.argv[1])

    if not script_dir.exists():
        print(f"错误：文件夹 {script_dir} 不存在")
        sys.exit(1)

    if not script_dir.is_dir():
        print(f"错误：{script_dir} 不是有效的文件夹")
        sys.exit(1)

    generate_submit_script(script_dir)