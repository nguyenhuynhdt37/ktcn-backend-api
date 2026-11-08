#!/usr/bin/env python3
"""Branch-bound, component-bound deployments through SSH forced commands."""
import copy
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid

ROOT = Path('/home/admin/KTCT/deploy')
COMPONENTS = {
    'backend': ('ktcn-backend-api', 'be_ktcn', 'backend', 'be_backend', 8000, '/health'),
    'frontend': ('ktcn-client-frontend', 'fe_client_ktcn', 'web', 'nextjs_portal', 3002, '/vi'),
    'admin': ('ktcn-admin-portal', 'admin_ktcn', 'web', 'ktcn_v2_web', 5177, '/'),
}
STAGE_PORTS = {'backend': 18000, 'frontend': 13002, 'admin': 15177}


def validate_image(component, image):
    repo = COMPONENTS[component][0]
    if not isinstance(image, str) or not re.fullmatch(
        rf'ghcr\.io/nguyenhuynhdt37/{repo}@sha256:[0-9a-f]{{64}}', image
    ):
        raise ValueError('Expected immutable digest in the component GHCR repository')
    return image


def validate_request(request, mode):
    match = re.fullmatch(r'(stage|prod)-(backend|frontend|admin)', mode)
    if not match:
        raise ValueError('Unsupported or retired SSH command mode')
    environment, component = match.groups()
    branch = 'dev' if environment == 'stage' else 'main'
    if request.get('component') != component:
        raise ValueError('SSH key is restricted to one component')
    if request.get('branch') != branch:
        raise ValueError('SSH key is restricted to branch ' + branch)
    if request.get('action') != 'deploy':
        raise ValueError('Only branch deployment is supported')
    commit = request.get('commit')
    if not isinstance(commit, str) or not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('Expected full Git commit SHA')
    validate_image(component, request.get('image'))
    return environment


def run(*args, **kwargs):
    return subprocess.run(list(args), check=True, text=True, **kwargs)


def load(path, default=None):
    return json.loads(path.read_text()) if path.exists() else copy.deepcopy(default)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    tmp.chmod(0o600)
    tmp.replace(path)


def current_commit(component, branch):
    repo = COMPONENTS[component][0]
    output = run('git', 'ls-remote', f'https://github.com/nguyenhuynhdt37/{repo}.git',
                 'refs/heads/' + branch, capture_output=True, timeout=30).stdout.strip()
    return output.split()[0] if output else ''


def stage_env(state):
    # Old state entries are accepted during the one-time transition to dev/main.
    return dict(os.environ, **{
        f'{name.upper()}_IMAGE': state.get(name, {}).get('image', state.get(name, {}).get('staging', 'unconfigured:never'))
        for name in COMPONENTS
    })


def stage_compose(state, *args):
    return run('docker', 'compose', '--project-directory', str(ROOT / 'staging'),
               '-f', str(ROOT / 'staging' / 'compose.yml'), *args, env=stage_env(state))


def prod_compose(component, image, *args):
    _, directory, service, _, _, _ = COMPONENTS[component]
    base = Path('/home/admin/KTCT') / directory
    override = ROOT / 'production' / f'{component}.override.json'
    override.parent.mkdir(parents=True, exist_ok=True)
    override.write_text(json.dumps({'services': {service: {'image': image}}}))
    return run('docker', 'compose', '--project-directory', str(base), '-p', directory,
               '-f', str(base / 'docker-compose.yml'), '-f', str(override), *args)


def ready(component, staging=False):
    port = STAGE_PORTS[component] if staging else COMPONENTS[component][4]
    for _ in range(45):
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}{COMPONENTS[component][5]}', timeout=4) as response:
                body = response.read()
                if response.status == 200 and (component != 'backend' or json.loads(body).get('status') == 'healthy'):
                    return
        except (OSError, ValueError):
            pass
        time.sleep(2)
    raise RuntimeError(f'{component} did not become healthy')


def record(environment, request, previous_image=None):
    info = {key: request[key] for key in ('component', 'branch', 'commit', 'image')}
    info['deployed_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
    if previous_image:
        info['previous_image'] = previous_image
    directory = ROOT / 'deployments'
    path = directory / f'{environment}-{request["component"]}.json'
    history = load(path, [])
    save(path, history + [info])
    return info


def backup_database():
    directory = ROOT / 'backups'
    directory.mkdir(mode=0o700, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d%H%M%S')
    path = directory / f'main-backend-{stamp}-{uuid.uuid4().hex[:8]}.dump'
    with path.open('wb') as stream:
        subprocess.run(['docker', 'exec', 'be_postgres', 'pg_dump', '-U', 'postgres',
                        '-d', 'university_cms', '-Fc'], stdout=stream, check=True)
    if path.stat().st_size == 0:
        raise RuntimeError('Empty database backup')
    print('Database backup:', path, flush=True)


def previous_production_image(component):
    image_id = run('docker', 'inspect', '--format', '{{.Image}}', COMPONENTS[component][3],
                   capture_output=True).stdout.strip()
    tag = f'ktcn-rollback/{component}:{image_id.removeprefix("sha256:")}'
    run('docker', 'image', 'tag', image_id, tag)
    return tag


def deploy_test(request):
    component = request['component']
    path = ROOT / 'staging-state.json'
    previous = load(path, {})
    state = copy.deepcopy(previous)
    state[component] = {key: request[key] for key in ('branch', 'commit', 'image')}
    try:
        if component == 'backend':
            stage_compose(state, 'run', '--rm', '--no-deps', 'backend', 'alembic', 'upgrade', 'head')
        stage_compose(state, 'up', '-d', '--no-deps', '--no-build', component)
        ready(component, staging=True)
    except Exception:
        if component in previous:
            stage_compose(previous, 'up', '-d', '--no-deps', '--no-build', component)
        raise
    save(path, state)
    record('staging', request)
    print('Dev test deployment healthy:', component, request['commit'], flush=True)


def deploy_production(request):
    component, image = request['component'], request['image']
    previous = previous_production_image(component)
    service = COMPONENTS[component][2]
    save(ROOT / 'production' / f'{component}-before.json', {'image': previous, 'target_commit': request['commit']})
    if component == 'backend':
        backup_database()
    try:
        if component == 'backend':
            prod_compose(component, image, 'run', '--rm', '--no-deps', 'backend', 'alembic', 'upgrade', 'head')
        prod_compose(component, image, 'up', '-d', '--no-deps', '--no-build', service)
        ready(component)
    except Exception:
        print('Deployment failed. Restoring previous application image; DB backup retained.', flush=True)
        prod_compose(component, previous, 'up', '-d', '--no-deps', '--no-build', service)
        ready(component)
        raise
    path = ROOT / 'production-state.json'
    state = load(path, {})
    state[component] = record('production', request, previous)
    save(path, state)
    print('Main production deployment healthy:', component, request['commit'], flush=True)


def deploy(request, environment):
    if current_commit(request['component'], request['branch']) != request['commit']:
        print('Skipping superseded build for branch', request['branch'], flush=True)
        return
    run('docker', 'pull', request['image'])
    if environment == 'stage':
        deploy_test(request)
    else:
        deploy_production(request)


def main():
    os.umask(0o077)
    mode = sys.argv[1] if len(sys.argv) == 2 else ''
    payload = sys.stdin.buffer.read(65537)
    if len(payload) > 65536:
        raise ValueError('Request too large')
    request = json.loads(payload)
    environment = validate_request(request, mode)
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / 'deploy.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        token = request.pop('registry_token', '')
        with tempfile.TemporaryDirectory(prefix='ktcn-docker-') as config:
            os.environ['DOCKER_CONFIG'] = config
            if token:
                actor = request.get('registry_user', '')
                if not re.fullmatch(r'[A-Za-z0-9\[\]-]+', actor):
                    raise ValueError('Invalid registry user')
                run('docker', 'login', 'ghcr.io', '--username', actor, '--password-stdin',
                    input=token, stdout=subprocess.DEVNULL)
            deploy(request, environment)


if __name__ == '__main__': main()
