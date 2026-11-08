from pathlib import Path
import os,subprocess,unittest

GUARD=Path(__file__).with_name('runner-guard.sh')
REPOS={'backend':('ktcn-backend-api','deploy.yml'),'frontend':('ktcn-client-frontend','ci.yml'),'admin':('ktcn-admin-portal','deploy.yml')}


class RunnerGuardTests(unittest.TestCase):
    def context(self,component='backend',branch='dev'):
        repo,workflow=REPOS[component]
        return dict(os.environ,GITHUB_REPOSITORY='nguyenhuynhdt37/'+repo,
            GITHUB_REF='refs/heads/'+branch,GITHUB_EVENT_NAME='push',
            GITHUB_WORKFLOW_REF=f'nguyenhuynhdt37/{repo}/.github/workflows/{workflow}@refs/heads/{branch}',
            GITHUB_JOB='deploy-test' if branch=='dev' else 'deploy-production')
    def check(self,env,component='backend'):
        return subprocess.run(['bash',str(GUARD),component],env=env,capture_output=True,text=True).returncode
    def test_each_component_accepts_dev_and_main(self):
        for c in REPOS:
            for branch in ['dev','main']:
                with self.subTest(component=c,branch=branch):self.assertEqual(self.check(self.context(c,branch),c),0)
    def test_branch_environment_mismatches_rejected(self):
        for branch,job in [('dev','deploy-production'),('main','deploy-test')]:
            env=self.context(branch=branch);env['GITHUB_JOB']=job
            self.assertNotEqual(self.check(env),0)
    def test_pull_requests_rejected_even_if_main_ref(self):
        for event in ['pull_request','pull_request_target']:
            env=self.context(branch='main');env['GITHUB_EVENT_NAME']=event
            self.assertNotEqual(self.check(env),0)
    def test_other_repository_cannot_use_runner(self):self.assertNotEqual(self.check(self.context('frontend'),'backend'),0)
    def test_other_workflow_and_build_job_rejected(self):
        for key,value in [('GITHUB_JOB','build'),('GITHUB_WORKFLOW_REF','nguyenhuynhdt37/ktcn-backend-api/.github/workflows/evil.yml@refs/heads/dev')]:
            env=self.context();env[key]=value;self.assertNotEqual(self.check(env),0)
    def test_legacy_promote_workflow_rejected(self):
        env=self.context(branch='main');env.update(GITHUB_JOB='deploy',GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_WORKFLOW_REF='nguyenhuynhdt37/ktcn-backend-api/.github/workflows/promote.yml@refs/heads/main')
        self.assertNotEqual(self.check(env),0)

if __name__=='__main__':unittest.main()
