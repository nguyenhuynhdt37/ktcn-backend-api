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
    oauth_path=KEYS/'tailscale.json'
    oauth=json.loads(oauth_path.read_text()) if oauth_path.exists() else {}
    client=os.getenv('TS_OAUTH_CLIENT_ID') or oauth.get('client_id','')
    credential=os.getenv('TS_OAUTH_SECRET') or oauth.get('client_secret','')
    for component,repo in REPOS.items():
        for environment in ['staging','production']:
            path=f'repos/{OWNER}/{repo}/environments/{environment}'
            policy={'deployment_branch_policy':{'protected_branches':False,'custom_branch_policies':True}}
            if environment=='production':
                policy.update({'reviewers':[{'type':'User','id':user['id']}],
                               'prevent_self_review':False,'can_admins_bypass':False})
            api(path,'PUT',policy)
            existing=api(path+'/deployment-branch-policies').get('branch_policies',[])
            if not any(p['name']=='main' and p.get('type','branch')=='branch' for p in existing):
                api(path+'/deployment-branch-policies','POST',{'name':'main','type':'branch'})
            key='production' if environment=='production' else component
            secret(repo,'DEPLOY_SSH_KEY',(KEYS/key).read_text(),environment)
            secret(repo,'DEPLOY_KNOWN_HOSTS',(KEYS/'known_hosts').read_text(),environment)
        if client and credential:
            secret(repo,'TS_OAUTH_CLIENT_ID',client)
            secret(repo,'TS_OAUTH_SECRET',credential)
        print(repo+': deployment environments and restricted SSH keys configured')
    if not client or not credential:
        raise SystemExit('Tailscale OAuth not set. Supply TS_OAUTH_CLIENT_ID/TS_OAUTH_SECRET or ~/.config/ktcn-deploy/tailscale.json, then run again.')
    print('GitHub deployment configuration complete. Verify tailnet tag:ktcn-ci can reach 100.122.190.92:22.')


if __name__=='__main__': main()
