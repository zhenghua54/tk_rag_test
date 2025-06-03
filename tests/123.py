import torch
print(torch.cuda.is_available())  # 是否能识别到GPU
print(torch.cuda.current_device())  # 显示当前设备ID
print(torch.cuda.get_device_name(0))  # 显示设备名称