#!/usr/bin/env python3
"""Run once as admin on webdeploy. Does not change production containers or rows."""
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess

ROOT = Path('/home/admin/KTCT/deploy')
STAGE = ROOT / 'staging'


def run(*args, **kwargs):
    return subprocess.run(list(args), check=True, **kwargs)


def write_env(path, values):
    if path.exists():
        return
    path.write_text(''.join(f'{k}={json.dumps(str(v))}\n' for k, v in values.items()))
    path.chmod(0o600)


def main():
    os.umask(0o077)
    STAGE.mkdir(parents=True, exist_ok=True, mode=0o700)
    (ROOT/'releases').mkdir(exist_ok=True, mode=0o700)
    source = Path(__file__).parent
    shutil.copyfile(source/'staging.compose.yml', STAGE/'compose.yml')
    if not (STAGE/'db.env').exists():
        password = secrets.token_hex(32)
        minio_password = secrets.token_hex(32)
        write_env(STAGE/'db.env', {'POSTGRES_DB':'university_cms_test',
            'POSTGRES_USER':'postgres','POSTGRES_PASSWORD':password})
        write_env(STAGE/'minio.env', {'MINIO_ROOT_USER':'ktcn_test','MINIO_ROOT_PASSWORD':minio_password})
        write_env(STAGE/'backend.env', {
            'PROJECT_NAME':'KTCT TEST', 'ENV':'staging', 'DEBUG':'false',
            'POSTGRES_SERVER':'db', 'POSTGRES_PORT':'5432','POSTGRES_USER':'postgres',
            'POSTGRES_PASSWORD':password,'POSTGRES_DB':'university_cms_test',
            'REDIS_HOST':'redis','REDIS_PORT':'6379','REDIS_PASSWORD':'','REDIS_DB':'0',
            'SECRET_KEY':secrets.token_hex(48),'COOKIE_SECURE':'true','COOKIE_SAMESITE':'lax',
            'BACKEND_CORS_ORIGINS':json.dumps(['https://test-ktcn.itup.io.vn',
                'https://test-admin-ktcn.itup.io.vn']),
            'MINIO_ENDPOINT':'test-media-ktcn.itup.io.vn','MINIO_INTERNAL_ENDPOINT':'test-media-ktcn.itup.io.vn',
            'MINIO_ACCESS_KEY':'ktcn_test','MINIO_SECRET_KEY':minio_password,
            'MINIO_SECURE':'true','MINIO_BUCKET':'ktcn-test-media',
            'AI_PROVIDER':'omniroute','AI_BASE_URL':'http://127.0.0.1:9',
            'AI_API_KEY':'disabled-in-test','GEMINI_API_KEY':'',
            'VAPID_PRIVATE_KEY':'','VAPID_PUBLIC_KEY':'',
        })
    placeholders = dict(os.environ, BACKEND_IMAGE='unconfigured:never',
                        FRONTEND_IMAGE='unconfigured:never', ADMIN_IMAGE='unconfigured:never')
    compose = ['docker','compose','--project-directory',str(STAGE),'-f',str(STAGE/'compose.yml')]
    run(*compose,'up','-d','--wait','db','redis','minio',env=placeholders)
    # Copy only DDL and migration metadata, never production users/content/tokens.
    marker=STAGE/'schema-initialized'
    if not marker.exists():
        cid=run(*compose,'ps','-q','db',env=placeholders,capture_output=True,text=True).stdout.strip()
        existing=run('docker','exec',cid,'psql','-U','postgres','-d','university_cms_test','-Atc',
            "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'",capture_output=True,text=True).stdout.strip()
        if existing != '0':
            raise RuntimeError('Test database already contains tables; refusing to overwrite')
        schema=run('docker','exec','be_postgres','pg_dump','-U','postgres','-d','university_cms',
                   '--schema-only','--no-owner','--no-privileges',capture_output=True).stdout
        version=run('docker','exec','be_postgres','pg_dump','-U','postgres','-d','university_cms',
                    '--data-only','--table=public.alembic_version','--no-owner','--no-privileges',capture_output=True).stdout
        run('docker','exec','-i',cid,'psql','-U','postgres','-d','university_cms_test',
            '-v','ON_ERROR_STOP=1',input=schema+version,stdout=subprocess.DEVNULL)
        marker.write_text('Production schema and migration version only; no application rows copied.\n')
    print('Test infrastructure initialized. Environment credentials stay on the server.')


if __name__ == '__main__':
    main()
