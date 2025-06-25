import os
import tempfile

def load_env_file(path):
    """
    .env 형식 파일을 읽어 key=value 형태의 딕셔너리로 반환
    주석(#)과 빈 줄은 무시
    """
    env_map = {}
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                env_map[key.strip()] = val.strip()
    return env_map

full_path = "dev.tfvars"

env_map = load_env_file(full_path)

for k, v in env_map.items():
    print(f"Key: {k}, Value: {v}")
