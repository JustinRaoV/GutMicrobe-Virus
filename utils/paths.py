import os

def get_paths(output, steps_name):
    """
    根据输出目录和步骤名生成各步骤的路径，文件夹带序号，如'1.trimmed'、'2.host_removed'等。
    """
    paths = {}
    for idx, step in enumerate(steps_name, 1):
        folder = f"{idx}.{step}"
        paths[step] = os.path.join(output, folder)
    return paths 