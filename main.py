import kopf
import kubernetes
import os
import tempfile
import subprocess
import shutil

@kopf.on.startup()
def startup(settings: kopf.OperatorSettings, **kwargs):
    # 클러스터 내부에서 동작하는 경우, in-cluster config 로드
    settings.posting.level = "INFO"
    kubernetes.config.load_incluster_config()

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

@kopf.on.create('argoproj.io', 'v1alpha1', 'rollouts')
@kopf.on.update('argoproj.io', 'v1alpha1', 'rollouts')
def inject_env_from_gitlab(spec, meta, namespace, logger, **kwargs):
    # Rollout의 metadata.annotations 를 가져옴
    annotations = meta.get('annotations', {})

    # 주입 활성화 조건 확인
    if annotations.get('env-inject.gitlab.io/enabled') != 'true':
        return

    # GitLab repo 관련 annotation 값
    repo_url = annotations.get('env-inject.gitlab.io/repo')
    file_path = annotations.get('env-inject.gitlab.io/path')
    branch = annotations.get('env-inject.gitlab.io/ref', 'main')  # ref가 없으면 기본값 main

    # 필수 값 누락 시 에러 반환
    if not repo_url or not file_path:
        raise kopf.PermanentError("repo와 path annotation이 필요합니다")

    # GitLab Access Token 은 환경변수로 주입되어야 함
    token = os.getenv('GITLAB_TOKEN')
    if not token:
        raise kopf.PermanentError("GITLAB_TOKEN 환경변수가 필요합니다")

    # GitLab repo URL 에 토큰 삽입 (https 인증 방식)
    repo_url_with_token = repo_url.replace('https://', f'https://oauth2:{token}@')

    # 임시 디렉터리 생성 후 Git clone
    tmpdir = tempfile.mkdtemp()
    try:
        subprocess.check_call(['git', 'clone', '--depth', '1', '--branch', branch, repo_url_with_token, tmpdir])

        full_path = os.path.join(tmpdir, file_path)
        if not os.path.isfile(full_path):
            raise kopf.PermanentError(f"{file_path} 파일이 GitLab repo에 존재하지 않습니다")

        # .env 파일을 파싱하여 key=value 딕셔너리 생성
        env_map = load_env_file(full_path)

        # Kubernetes API 객체 생성
        api = kubernetes.client.CustomObjectsApi()

        # 현재 Rollout 리소스를 가져옴
        rollout = api.get_namespaced_custom_object(
            group="argoproj.io",
            version="v1alpha1",
            namespace=namespace,
            plural="rollouts",
            name=meta['name']
        )

        # 첫 번째 컨테이너 기준으로 env 항목 처리
        containers = rollout['spec']['template']['spec']['containers']
        env_list = containers[0].get('env', [])

        # 중복 방지를 위한 기존 env 변수 키 모음
        existing_keys = {e.get('name') for e in env_list}

        # .env 로드된 key=value 를 직접 env 항목에 추가
        for k, v in env_map.items():
            if k not in existing_keys:
                env_list.append({
                    "name": k,
                    "value": v
                })

        # containers[0] 에 수정된 env 적용
        containers[0]['env'] = env_list

        # patch 요청 body 구성
        patch_body = {
            "spec": {
                "template": {
                    "spec": {
                        "containers": containers
                    }
                }
            }
        }

        # Rollout 리소스 patch 수행 (env 주입)
        api.patch_namespaced_custom_object(
            group="argoproj.io",
            version="v1alpha1",
            namespace=namespace,
            plural="rollouts",
            name=meta['name'],
            body=patch_body
        )

        logger.info(f"{meta['name']} Rollout에 GitLab env 변수들을 주입했습니다")

    finally:
        # 임시 디렉터리 정리
        shutil.rmtree(tmpdir)