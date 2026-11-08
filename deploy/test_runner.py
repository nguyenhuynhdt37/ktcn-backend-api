from pathlib import Path
import os
import subprocess
import unittest

GUARD=Path(__file__).with_name('runner-guard.sh')
REPOS={'backend':('ktcn-backend-api','deploy.yml'),'frontend':('ktcn-client-frontend','ci.yml'),'admin':('ktcn-admin-portal','deploy.yml')}


class RunnerGuardTests(unittest.TestCase):
    def context(self,component='backend'):
        repo,workflow=REPOS[component]
        return dict(os.environ,GITHUB_REPOSITORY='nguyenhuynhdt37/'+repo,
            GITHUB_REF='refs/heads/main',GITHUB_EVENT_NAME='push',
            GITHUB_WORKFLOW_REF=f'nguyenhuynhdt37/{repo}/.github/workflows/{workflow}@refs/heads/main',
            GITHUB_JOB='deploy-test')

    def check(self,env,component='backend'):
        return subprocess.run(['bash',str(GUARD),component],env=env,capture_output=True,text=True).returncode

    def test_each_component_accepts_its_main_deploy(self):
        for component in REPOS:
            with self.subTest(component=component): self.assertEqual(self.check(self.context(component),component),0)

    def test_pull_request_ref_is_rejected(self):
        env=self.context();env['GITHUB_REF']='refs/pull/42/merge'
        self.assertNotEqual(self.check(env),0)

    def test_pull_request_target_on_main_is_rejected(self):
        env=self.context();env['GITHUB_EVENT_NAME']='pull_request_target'
        self.assertNotEqual(self.check(env),0)

    def test_other_repository_cannot_use_runner(self):
        env=self.context('frontend')
        self.assertNotEqual(self.check(env,'backend'),0)

    def test_other_workflow_and_build_job_rejected(self):
        for key,value in [('GITHUB_JOB','build'),('GITHUB_WORKFLOW_REF','nguyenhuynhdt37/ktcn-backend-api/.github/workflows/evil.yml@refs/heads/main')]:
            with self.subTest(key=key):
                env=self.context();env[key]=value
                self.assertNotEqual(self.check(env),0)

    def test_manual_production_requires_dispatch(self):
        env=self.context();env.update(GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_JOB='deploy',GITHUB_WORKFLOW_REF='nguyenhuynhdt37/ktcn-backend-api/.github/workflows/promote.yml@refs/heads/main')
        self.assertEqual(self.check(env),0)
        env['GITHUB_EVENT_NAME']='push'
        self.assertNotEqual(self.check(env),0)


if __name__=='__main__': unittest.main()
