#!/usr/bin/env python3
"""Root-owned forced command. Accept only a component and short-lived GitHub registration token."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

REPOS={'backend':'ktcn-backend-api','frontend':'ktcn-client-frontend','admin':'ktcn-admin-portal'}


def main():
    if os.geteuid()!=0:
        raise SystemExit('Run as root')
    payload=sys.stdin.buffer.read(4097)
    if len(payload)>4096: raise SystemExit('Payload too large')
    request=json.loads(payload)
    component=request.get('component'); token=request.get('token','')
    if component not in REPOS or not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{10,256}',token):
        raise SystemExit('Invalid registration request')
    directory=Path('/var/lib/ktcn-runners')/component/'runner'
    if not directory.is_dir(): raise SystemExit('Runner application is not installed')
    if not (directory/'.runner').exists():
        command=['runuser','-u','ktcn-runner-'+component,'--',str(directory/'config.sh'),
            '--url','https://github.com/nguyenhuynhdt37/'+REPOS[component],
            '--token',token,'--unattended','--name','webdeploy-ktcn-'+component,
            '--labels','ktcn-deploy,ktcn-'+component,'--work','_work']
        result=subprocess.run(command,cwd=directory,text=True,capture_output=True)
        if result.returncode:
            print((result.stdout+result.stderr).replace(token,'[REDACTED]')[-3000:])
            raise SystemExit('Runner registration failed')
    subprocess.run(['systemctl','enable','--now','ktcn-runner-'+component+'.service'],check=True)
    print('Registered and started runner for',component)


if __name__=='__main__': main()
