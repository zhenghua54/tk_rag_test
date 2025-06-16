from modelscope.hub.snapshot_download import snapshot_download

model_dir = snapshot_download(
    model_id='Qwen/Qwen2.5-14B-Instruct-1M',
    local_dir='~/Qwen/Qwen2.5-14B-DeepSeek-R1-1M'
)