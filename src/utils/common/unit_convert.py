# 将字节转换为 ​KiB/MiB/GiB​ 等
def convert_bytes(size: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB"]
    index = 0
    while size >= 1024 and index < len(units)-1:
        size /= 1024
        index += 1
    return f"{size:.2f} {units[index]}"