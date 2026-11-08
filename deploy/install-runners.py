#!/usr/bin/env python3
"""Prepare three unprivileged GitHub deployment runners. Registration is a separate step."""
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import urllib.request

TOOLS=Path('/opt/ktcn-runner-tools')
BASE=Path('/var/lib/ktcn-runners')
COMPONENTS=['backend','frontend','admin']


def run(*args,**kwargs):
    return subprocess.run(list(args),check=True,**kwargs)


def download(url,target):
    request=urllib.request.Request(url,headers={'User-Agent':'KTCT-runner-setup'})
    with urllib.request.urlopen(request,timeout=90) as source,target.open('wb') as output:
        shutil.copyfileobj(source,output)


def main():
    if os.geteuid()!=0: raise SystemExit('Run with sudo')
    if os.uname().machine!='x86_64': raise SystemExit('This installer targets Linux AMD64')
    source=Path(__file__).parent
    TOOLS.mkdir(parents=True,exist_ok=True,mode=0o755)
    (TOOLS/'guards').mkdir(exist_ok=True,mode=0o755)
    for name in ['runner-guard.sh','register-runner.py']:
        p=TOOLS/name;shutil.copyfile(source/name,p);p.chmod(0o755)
    request=urllib.request.Request('https://api.github.com/repos/actions/runner/releases/latest',headers={'User-Agent':'KTCT-runner-setup'})
    with urllib.request.urlopen(request,timeout=30) as response:
        release=json.load(response)
    asset=next(a for a in release['assets'] if a['name'].startswith('actions-runner-linux-x64-') and a['name'].endswith('.tar.gz'))
    digest=asset.get('digest','')
    if not digest.startswith('sha256:'): raise SystemExit('GitHub release does not provide a SHA256 digest; refusing unverified install')
    cache=Path('/var/cache/ktcn-runners');cache.mkdir(exist_ok=True,mode=0o700)
    archive=cache/asset['name']
    print('Preparing official GitHub runner',release['tag_name'],flush=True)
    if not archive.exists(): download(asset['browser_download_url'],archive)
    actual=hashlib.file_digest(archive.open('rb'),'sha256').hexdigest() if hasattr(hashlib,'file_digest') else hashlib.sha256(archive.read_bytes()).hexdigest()
    if actual!=digest.removeprefix('sha256:'): raise SystemExit('Runner checksum mismatch')
    BASE.mkdir(parents=True,exist_ok=True,mode=0o755)
    for component in COMPONENTS:
        username='ktcn-runner-'+component
        home=BASE/component
        try: account=pwd.getpwnam(username)
        except KeyError:
            run('useradd','--system','--user-group','--create-home','--home-dir',str(home),'--shell','/usr/sbin/nologin',username)
            account=pwd.getpwnam(username)
        home.chmod(0o700)
        directory=home/'runner';directory.mkdir(exist_ok=True)
        if not (directory/'bin/Runner.Listener').exists():
            run('tar','-xzf',str(archive),'-C',str(directory),'--no-same-owner')
            run('chown','-R',f'{account.pw_uid}:{account.pw_gid}',str(home))
        wrapper=TOOLS/'guards'/f'{component}.sh'
        wrapper.write_text('#!/usr/bin/env bash\nexec /bin/bash /opt/ktcn-runner-tools/runner-guard.sh '+component+'\n');wrapper.chmod(0o755)
        unit=f'''[Unit]
Description=KTCT {component} GitHub deployment runner
After=network-online.target
Wants=network-online.target
ConditionPathExists={directory}/.runner

[Service]
Type=simple
User={username}
Group={username}
WorkingDirectory={directory}
Environment=HOME={home}
Environment=ACTIONS_RUNNER_HOOK_JOB_STARTED={wrapper}
ExecStart={directory}/run.sh
Restart=on-failure
RestartSec=10
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectHome=true
ProtectSystem=strict
ReadWritePaths={home}
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
CapabilityBoundingSet=
MemoryMax=384M
CPUQuota=30%

[Install]
WantedBy=multi-user.target
'''
        Path('/etc/systemd/system',f'ktcn-runner-{component}.service').write_text(unit)
        print('Prepared',username,'(no Docker/admin membership)',flush=True)
    run('systemctl','daemon-reload')
    # Confirm native runner libraries are installed. This does not register or run a job.
    first=BASE/'backend/runner/bin/Runner.Listener'
    run('runuser','-u','ktcn-runner-backend','--',str(first),'--version')
    print('Runner services prepared; awaiting short-lived GitHub registration tokens.',flush=True)


if __name__=='__main__': main()
