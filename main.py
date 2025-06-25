import kopf
import kubernetes
import os
import tempfile
import subprocess
import shutil

@kopf.on.create('apps', 'v1', 'replicasets')
@kopf.on.update('apps', 'v1', 'replicasets')
def inject_env_from_gitlab_rs(spec, meta, namespace, logger, **kwargs):
    annotations = spec.get('template', {}).get('metadata', {}).get('annotations', {})

    if annotations.get('env-inject.gitlab.io/enabled') != 'true':
        return

    # GitLab 관련 파라미터
    repo_url = annotations.get('env-inject.gitlab.io/repo')
    file_path = annotations.get('env-inject.gitlab.io/path')
    branch = annotations.get('env-inject.gitlab.io/ref', 'main')

    logger.info(f"repo_url:{repo_url}")
    logger.info(f"file_path:{file_path}")
    logger.info(f"branch:{branch}")

    if not repo_url or not file_path:
        raise kopf.PermanentError("repo와 path annotation이 필요합니다")

    token = os.getenv('GITLAB_TOKEN')
    logger.info(f"token:{token}")
    if not token:
        raise kopf.PermanentError("GITLAB_TOKEN 환경변수가 필요합니다")

    # GitLab clone 및 .env 파일 파싱
    repo_url_with_token = repo_url.replace("https://", f"https://oauth2:{token}@")
    tmpdir = tempfile.mkdtemp()

    try:
        subprocess.check_call(['git', 'clone', '--depth', '1', '--branch', branch, repo_url_with_token, tmpdir])
        env_map = load_env_file(os.path.join(tmpdir, file_path))
    finally:
        shutil.rmtree(tmpdir)

    containers = spec.get('template', {}).get('spec', {}).get('containers', [])
    env_list = containers[0].get('env', [])
    existing_keys = {e['name'] for e in env_list}

    for k, v in env_map.items():
        if k not in existing_keys:
            env_list.append({"name": k, "value": v})

    containers[0]['env'] = env_list

    patch_body = {
        "spec": {
            "template": {
                "spec": {
                    "containers": containers
                }
            }
        }
    }

    api = kubernetes.client.AppsV1Api()
    api.patch_namespaced_replica_set(
        name=meta['name'],
        namespace=namespace,
        body=patch_body
    )

    logger.info(f"{meta['name']} ReplicaSet에 env 주입 완료")


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