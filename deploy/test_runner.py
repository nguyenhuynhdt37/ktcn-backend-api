import os
import shutil
import subprocess
import unittest
from pathlib import Path

GUARD = Path(__file__).with_name('runner-guard.sh')
REPOS = {
    'backend': ('ktcn-backend-api', 'deploy.yml'),
    'frontend': ('ktcn-client-frontend', 'ci.yml'),
    'admin': ('ktcn-admin-portal', 'deploy.yml'),
}


def _find_posix_bash() -> str | None:
    if os.name == 'nt':
        program_files = os.environ.get('PROGRAMFILES', r'C:\Program Files')
        git_bash = Path(program_files) / 'Git' / 'bin' / 'bash.exe'
        if git_bash.exists():
            return str(git_bash)
        return None
    return shutil.which('bash')


BASH_BIN = _find_posix_bash()


@unittest.skipIf(BASH_BIN is None, 'POSIX bash is required to test runner-guard.sh')
class RunnerGuardTests(unittest.TestCase):
    def context(
        self, component: str = 'backend', branch: str = 'dev'
    ) -> dict[str, str]:
        repo, workflow = REPOS[component]
        wf_ref = (
            f'nguyenhuynhdt37/{repo}/.github/workflows/{workflow}'
            f'@refs/heads/{branch}'
        )
        return dict(
            os.environ,
            GITHUB_REPOSITORY='nguyenhuynhdt37/' + repo,
            GITHUB_REF='refs/heads/' + branch,
            GITHUB_EVENT_NAME='push',
            GITHUB_WORKFLOW_REF=wf_ref,
            GITHUB_JOB='deploy-test' if branch == 'dev' else 'deploy-production',
        )

    def check(self, env: dict[str, str], component: str = 'backend') -> int:
        assert BASH_BIN is not None
        if os.name == 'nt':
            script = GUARD.read_text(encoding='utf-8').replace('\r\n', '\n')
            return subprocess.run(
                [BASH_BIN, '-s', '--', component],
                input=script,
                env=env,
                capture_output=True,
                text=True,
            ).returncode
        return subprocess.run(
            [BASH_BIN, str(GUARD), component],
            env=env,
            capture_output=True,
            text=True,
        ).returncode

    def test_each_component_accepts_dev_and_main(self) -> None:
        for c in REPOS:
            for branch in ['dev', 'main']:
                with self.subTest(component=c, branch=branch):
                    self.assertEqual(self.check(self.context(c, branch), c), 0)

    def test_branch_environment_mismatches_rejected(self) -> None:
        for branch, job in [('dev', 'deploy-production'), ('main', 'deploy-test')]:
            env = self.context(branch=branch)
            env['GITHUB_JOB'] = job
            self.assertNotEqual(self.check(env), 0)

    def test_pull_requests_rejected_even_if_main_ref(self) -> None:
        for event in ['pull_request', 'pull_request_target']:
            env = self.context(branch='main')
            env['GITHUB_EVENT_NAME'] = event
            self.assertNotEqual(self.check(env), 0)

    def test_other_repository_cannot_use_runner(self) -> None:
        self.assertNotEqual(self.check(self.context('frontend'), 'backend'), 0)

    def test_other_workflow_and_build_job_rejected(self) -> None:
        evil_wf = (
            'nguyenhuynhdt37/ktcn-backend-api/.github/workflows/evil.yml'
            '@refs/heads/dev'
        )
        for key, value in [
            ('GITHUB_JOB', 'build'),
            ('GITHUB_WORKFLOW_REF', evil_wf),
        ]:
            env = self.context()
            env[key] = value
            self.assertNotEqual(self.check(env), 0)

    def test_legacy_promote_workflow_rejected(self) -> None:
        promote_wf = (
            'nguyenhuynhdt37/ktcn-backend-api/.github/workflows/promote.yml'
            '@refs/heads/main'
        )
        env = self.context(branch='main')
        env.update(
            GITHUB_JOB='deploy',
            GITHUB_EVENT_NAME='workflow_dispatch',
            GITHUB_WORKFLOW_REF=promote_wf,
        )
        self.assertNotEqual(self.check(env), 0)


if __name__ == '__main__':
    unittest.main()
