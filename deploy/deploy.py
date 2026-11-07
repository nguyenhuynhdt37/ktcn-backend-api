#!/usr/bin/env python3
"""Installed on webdeploy; SSH forced commands constrain stage/production keys.

Receive one bounded JSON request on stdin. Never execute remote shell input.
State and config live outside source checkouts, at /home/admin/KTCT/deploy.
"""
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
        raise ValueError('Expected an immutable image digest in the component GHCR repository')
    return image


def validate_request(request, mode):
    if mode.startswith('stage-'):
        component = mode.removeprefix('stage-')
        if component not in COMPONENTS or request.get('component') != component:
            raise ValueError('SSH key is restricted to one component')
        if not re.fullmatch('[0-9a-f]{40}', request.get('commit', '')):
            raise ValueError('Expected full Git commit SHA')
        validate_image(component, request.get('staging'))
        validate_image(component, request.get('production'))
        if request.get('action') != 'stage':
            raise ValueError('Staging key cannot promote or roll back production')
    elif mode == 'production':
        if request.get('action') not in ('promote', 'rollback'):
            raise ValueError('Unsupported production command')
        if not re.fullmatch(r'[0-9]{14}-[0-9a-f]{12}', request.get('release', '')):
            raise ValueError('Invalid release ID')
    else:
        raise ValueError('Unknown key mode')


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


def stage_env(state):
    return dict(os.environ, **{
        f'{name.upper()}_IMAGE': state.get(name, {}).get('staging', 'unconfigured:never')
        for name in COMPONENTS
    })


def stage_compose(state, *args):
    return run('docker', 'compose', '--project-directory', str(ROOT / 'staging'),
               '-f', str(ROOT / 'staging' / 'compose.yml'), *args, env=stage_env(state))


def ready(component, staging=False):
    port = STAGE_PORTS[component] if staging else COMPONENTS[component][4]
    path = COMPONENTS[component][5]
    for _ in range(45):
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}{path}', timeout=4) as response:
                body = response.read()
                if response.status == 200:
                    if component != 'backend' or json.loads(body).get('status') == 'healthy':
                        return
        except (OSError, ValueError):
            pass
        time.sleep(2)
    raise RuntimeError(f'{component} did not become healthy')


def prod_compose(component, image, *args):
    _, directory, service, _, _, _ = COMPONENTS[component]
    base = Path('/home/admin/KTCT') / directory
    override = ROOT / 'production' / f'{component}.override.json'
    override.parent.mkdir(parents=True, exist_ok=True)
    override.write_text(json.dumps({'services': {service: {'image': image}}}))
    return run('docker', 'compose', '--project-directory', str(base), '-p', directory,
               '-f', str(base / 'docker-compose.yml'), '-f', str(override), *args)


def deployed_images():
    images = {}
    for name, info in COMPONENTS.items():
        image_id = run('docker', 'inspect', '--format', '{{.Image}}', info[3],
                       capture_output=True).stdout.strip()
        # Give the old image a durable local tag, preserving the first rollback baseline.
        tag = f'ktcn-rollback/{name}:{image_id.removeprefix("sha256:")}'
        run('docker', 'image', 'tag', image_id, tag)
        images[name] = tag
    return images


def backup_database(release):
    directory = ROOT / 'backups'
    directory.mkdir(mode=0o700, exist_ok=True)
    path = directory / f'{release}-{uuid.uuid4().hex[:8]}.dump'
    with path.open('wb') as stream:
        subprocess.run(['docker', 'exec', 'be_postgres', 'pg_dump', '-U', 'postgres',
                        '-d', 'university_cms', '-Fc'], stdout=stream, check=True)
    if path.stat().st_size == 0:
        raise RuntimeError('Empty database backup')
    print('Database backup:', path, flush=True)


def get_release(release):
    data = load(ROOT / 'releases' / f'{release}.json')
    if not data or set(data.get('components', {})) != set(COMPONENTS):
        raise ValueError('Release has not passed checks for all three components')
    for component, info in data['components'].items():
        validate_image(component, info['production'])
        validate_image(component, info['staging'])
    return data


def stage(request):
    component = request['component']
    path = ROOT / 'staging-state.json'
    previous = load(path, {})
    state = copy.deepcopy(previous)
    state[component] = {k: request[k] for k in ('commit', 'staging', 'production')}
    # Invalidate the prior review candidate before touching the running test stack.
    (ROOT / 'candidate.json').unlink(missing_ok=True)
    run('docker', 'pull', request['staging'])
    run('docker', 'pull', request['production'])
    try:
        if component == 'backend':
            stage_compose(state, 'run', '--rm', '--no-deps', 'backend', 'alembic', 'upgrade', 'head')
        stage_compose(state, 'up', '-d', '--no-deps', '--no-build', component)
        ready(component, staging=True)
        save(path, state)
        if set(state) != set(COMPONENTS):
            print('Staging component healthy; awaiting other components:', ','.join(set(COMPONENTS)-set(state)))
            return
        for name in COMPONENTS:
            ready(name, staging=True)
        release = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d%H%M%S') + '-' + uuid.uuid4().hex[:12]
        manifest = {'release': release, 'components': state,
                    'tested_at': dt.datetime.now(dt.timezone.utc).isoformat()}
        save(ROOT / 'releases' / f'{release}.json', manifest)
        save(ROOT / 'candidate.json', manifest)
        print('RELEASE_ID=' + release, flush=True)
        print('Review https://test-ktcn.itup.io.vn/vi and https://test-admin-ktcn.itup.io.vn/')
    except Exception:
        # Schema changes are never auto-downgraded. A failed candidate cannot be promoted.
        if component in previous:
            stage_compose(previous, 'up', '-d', '--no-deps', '--no-build', component)
        raise


def apply_production(images, migrate=False):
    if migrate:
        prod_compose('backend', images['backend'], 'run', '--rm', '--no-deps',
                     'backend', 'alembic', 'upgrade', 'head')
    for name in COMPONENTS:
        service = COMPONENTS[name][2]
        prod_compose(name, images[name], 'up', '-d', '--no-deps', '--no-build', service)
        ready(name)


def production(request):
    release = request['release']
    data = get_release(release)
    if request['action'] == 'promote':
        candidate = load(ROOT / 'candidate.json')
        if not candidate or candidate['release'] != release:
            raise ValueError('Test stack changed: review and promote the latest release ID')
        for name in COMPONENTS:
            ready(name, staging=True)
    else:
        deployed = load(ROOT / 'production-history.json', [])
        if release not in deployed:
            raise ValueError('Rollback target was never deployed to production')
    images = {name: item['production'] for name, item in data['components'].items()}
    for image in images.values():
        found = subprocess.run(['docker', 'image', 'inspect', image], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if found.returncode != 0:
            run('docker', 'pull', image)
    previous = deployed_images()
    save(ROOT / 'production-before.json', {'release': release, 'images': previous})
    backup_database(release)
    try:
        apply_production(images, migrate=request['action'] == 'promote')
    except Exception:
        print('Deployment failed. Restoring prior application images; database backup retained.', flush=True)
        apply_production(previous)
        raise
    save(ROOT / 'production-current.json', data)
    history = load(ROOT / 'production-history.json', [])
    save(ROOT / 'production-history.json', list(dict.fromkeys(history + [release])))
    print('Production healthy. Release:', release, flush=True)
    print('Database schema is not automatically downgraded during rollback.')


def main():
    os.umask(0o077)
    mode = sys.argv[1] if len(sys.argv) == 2 else ''
    payload = sys.stdin.buffer.read(65537)
    if len(payload) > 65536:
        raise ValueError('Request too large')
    request = json.loads(payload)
    validate_request(request, mode)
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / 'deploy.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        # Registry credentials exist only in a temporary Docker config. Never log tokens.
        token = request.pop('registry_token', '')
        with tempfile.TemporaryDirectory(prefix='ktcn-docker-') as config:
            os.environ['DOCKER_CONFIG'] = config
            if token:
                actor = request.get('registry_user', '')
                if not re.fullmatch(r'[A-Za-z0-9\[\]-]+', actor):
                    raise ValueError('Invalid registry user')
                run('docker', 'login', 'ghcr.io', '--username', actor, '--password-stdin',
                    input=token, stdout=subprocess.DEVNULL)
            if mode.startswith('stage-'):
                stage(request)
            else:
                production(request)


if __name__ == '__main__':
    main()
