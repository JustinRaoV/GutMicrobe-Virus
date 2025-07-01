import os

def get_paths(output, steps):
    """
    根据 steps 列表自动生成以自增编号为前缀的目录字典。
    例如 steps = ["trimmed", "host_removed", "assembly"]
    返回：
    {
        "trimmed": os.path.join(output, "1.trimmed"),
        "host_removed": os.path.join(output, "2.host_removed"),
        "assembly": os.path.join(output, "3.assembly")
    }
    """
    return {
        step: os.path.join(output, f"{i+1}.{step}")
        for i, step in enumerate(steps)
    } 