#!/usr/bin/env python3
"""Run locally after gh auth login. Never print or commit credential values."""
import json
import os
from pathlib import Path
import subprocess

OWNER='nguyenhuynhdt37'
REPOS={'backend':'ktcn-backend-api','frontend':'ktcn-client-frontend','admin':'ktcn-admin-portal'}
KEYS=Path(os.getenv('KTCT_KEY_DIR',str(Path.home()/'.config/ktcn-deploy')))


def gh(*args,input=None):
    return subprocess.run(['gh',*args],input=input,text=True,capture_output=True,check=True).stdout


def api(path,method='GET',payload=None):
    args=['api',path,'--method',method]
    if payload is not None:
        args+=['--input','-']
    return json.loads(gh(*args,input=json.dumps(payload) if payload is not None else None) or '{}')


def secret(repo,name,value,environment=None):
    args=['secret','set',name,'--repo',f'{OWNER}/{repo}']
    if environment: args+=['--env',environment]
    gh(*args,input=value)


def main():
    user=api('user')
    if user['login'] != OWNER:
        raise SystemExit(f'Log in as {OWNER}; current GitHub login is {user["login"]}')
    for component,repo in REPOS.items():
        for environment,branch in [('staging','dev'),('production','main')]:
            path=f'repos/{OWNER}/{repo}/environments/{environment}'
            policy={'deployment_branch_policy':{'protected_branches':False,'custom_branch_policies':True},
                    'reviewers':[],'wait_timer':0,'prevent_self_review':False,'can_admins_bypass':False}
            api(path,'PUT',policy)
            existing=api(path+'/deployment-branch-policies').get('branch_policies',[])
            for item in existing:
                if item['name']!=branch or item.get('type','branch')!='branch':
                    api(path+'/deployment-branch-policies/'+str(item['id']),'DELETE')
            if not any(p['name']==branch and p.get('type','branch')=='branch' for p in existing):
                api(path+'/deployment-branch-policies','POST',{'name':branch,'type':'branch'})
            key='prod-'+component if environment=='production' else component
            secret(repo,'DEPLOY_SSH_KEY',(KEYS/key).read_text(),environment)
            secret(repo,'DEPLOY_KNOWN_HOSTS',(KEYS/'known_hosts').read_text(),environment)
        token=api(f'repos/{OWNER}/{repo}/actions/runners/registration-token','POST')['token']
        payload=json.dumps({'component':component,'token':token})
        args=['ssh','-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
              '-i',str(KEYS/'runner-register'),'admin@100.122.190.92','register']
        result=subprocess.run(args,input=payload,text=True,capture_output=True)
        if result.returncode:
            raise SystemExit('Runner registration failed: '+(result.stdout+result.stderr).replace(token,'[REDACTED]'))
        print(repo+': dev -> staging; main -> production; no deployment approval required')
    print('GitHub deployment configuration complete; no VPN credentials required.')


if __name__=='__main__': main()
