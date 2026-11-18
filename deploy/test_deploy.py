import importlib.util
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import call, patch

spec = importlib.util.spec_from_file_location(
    'deploy', Path(__file__).with_name('deploy.py')
)
assert spec is not None and spec.loader is not None
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class DeploymentTests(unittest.TestCase):
    def request(
        self, component: str = 'backend', branch: str = 'dev'
    ) -> dict[str, Any]:
        repo = deploy.COMPONENTS[component][0]
        return {
            'action': 'deploy',
            'component': component,
            'branch': branch,
            'commit': 'b' * 40,
            'image': f'ghcr.io/nguyenhuynhdt37/{repo}@sha256:' + 'a' * 64,
        }

    def test_branch_bound_keys_accept_correct_requests(self) -> None:
        self.assertEqual(
            deploy.validate_request(self.request(), 'stage-backend'), 'stage'
        )
        self.assertEqual(
            deploy.validate_request(self.request(branch='main'), 'prod-backend'),
            'prod',
        )

    def test_test_key_cannot_deploy_main(self) -> None:
        with self.assertRaises(ValueError):
            deploy.validate_request(self.request(branch='main'), 'stage-backend')

    def test_production_key_cannot_deploy_dev(self) -> None:
        with self.assertRaises(ValueError):
            deploy.validate_request(self.request(), 'prod-backend')

    def test_key_is_bound_to_component(self) -> None:
        with self.assertRaises(ValueError):
            deploy.validate_request(self.request(), 'stage-admin')
        with self.assertRaises(ValueError):
            deploy.validate_request(self.request(branch='main'), 'prod-admin')

    def test_legacy_production_key_mode_is_retired(self) -> None:
        with self.assertRaises(ValueError):
            deploy.validate_request(self.request(branch='main'), 'production')

    def test_mutable_foreign_and_wrong_component_images_rejected(self) -> None:
        images = [
            'ghcr.io/nguyenhuynhdt37/ktcn-backend-api:latest',
            'ghcr.io/attacker/backend@sha256:' + 'a' * 64,
            'ghcr.io/nguyenhuynhdt37/ktcn-admin-portal@sha256:' + 'a' * 64,
        ]
        for image in images:
            with self.subTest(image=image), self.assertRaises(ValueError):
                deploy.validate_image('backend', image)

    def test_malformed_commits_rejected_before_execution(self) -> None:
        for commit in ['main', '$(id)', None, 'b' * 39]:
            value = self.request()
            value['commit'] = commit
            with self.subTest(commit=commit), self.assertRaises(ValueError):
                deploy.validate_request(value, 'stage-backend')

    def test_superseded_build_has_no_side_effects(self) -> None:
        with (
            patch.object(deploy, 'current_commit', return_value='c' * 40),
            patch.object(deploy, 'run') as run,
            patch.object(deploy, 'deploy_test') as stage,
        ):
            deploy.deploy(self.request(), 'stage')
            run.assert_not_called()
            stage.assert_not_called()

    def test_main_routes_only_to_production(self) -> None:
        value = self.request(branch='main')
        with (
            patch.object(deploy, 'current_commit', return_value='b' * 40) as current,
            patch.object(deploy, 'run'),
            patch.object(deploy, 'deploy_test') as stage,
            patch.object(deploy, 'deploy_production') as prod,
        ):
            deploy.deploy(value, 'prod')
            current.assert_called_once_with('backend', 'main')
            stage.assert_not_called()
            prod.assert_called_once_with(value)

    def test_dev_routes_only_to_test(self) -> None:
        value = self.request()
        with (
            patch.object(deploy, 'current_commit', return_value='b' * 40),
            patch.object(deploy, 'run'),
            patch.object(deploy, 'deploy_test') as stage,
            patch.object(deploy, 'deploy_production') as prod,
        ):
            deploy.deploy(value, 'stage')
            stage.assert_called_once_with(value)
            prod.assert_not_called()

    def test_dev_update_preserves_other_component_images(self) -> None:
        value = self.request('frontend')
        previous = {
            'backend': {'staging': 'old-backend'},
            'admin': {'image': 'old-admin'},
        }
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(deploy, 'ROOT', Path(directory)),
            patch.object(deploy, 'stage_compose'),
            patch.object(deploy, 'ready'),
            patch.object(deploy, 'record'),
        ):
            deploy.save(Path(directory) / 'staging-state.json', previous)
            deploy.deploy_test(value)
            state = deploy.load(Path(directory) / 'staging-state.json')
            self.assertEqual(state['backend'], previous['backend'])
            self.assertEqual(state['admin'], previous['admin'])
            self.assertEqual(deploy.stage_env(state)['BACKEND_IMAGE'], 'old-backend')
            self.assertEqual(state['frontend']['branch'], 'dev')

    def test_backend_production_backs_up_before_migration(self) -> None:
        calls: list[str] = []
        value = self.request(branch='main')
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(deploy, 'ROOT', Path(directory)),
            patch.object(deploy, 'previous_production_image', return_value='previous'),
            patch.object(
                deploy, 'backup_database', side_effect=lambda: calls.append('backup')
            ),
            patch.object(
                deploy,
                'prod_compose',
                side_effect=lambda *a: calls.append(
                    'migration' if 'run' in a else 'replace'
                ),
            ),
            patch.object(deploy, 'ready'),
        ):
            deploy.deploy_production(value)
            self.assertEqual(calls, ['backup', 'migration', 'replace'])
            prod_state = deploy.load(Path(directory) / 'production-state.json')
            self.assertEqual(prod_state['backend']['branch'], 'main')

    def test_frontend_production_does_not_touch_database(self) -> None:
        value = self.request('frontend', 'main')
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(deploy, 'ROOT', Path(directory)),
            patch.object(deploy, 'previous_production_image', return_value='previous'),
            patch.object(deploy, 'backup_database') as backup,
            patch.object(deploy, 'prod_compose') as compose,
            patch.object(deploy, 'ready'),
        ):
            deploy.deploy_production(value)
            backup.assert_not_called()
            compose.assert_called_once_with(
                'frontend', value['image'], 'up', '-d', '--no-deps', '--no-build', 'web'
            )

    def test_failed_production_restores_only_changed_component(self) -> None:
        value = self.request('admin', 'main')
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(deploy, 'ROOT', Path(directory)),
            patch.object(deploy, 'previous_production_image', return_value='previous'),
            patch.object(deploy, 'prod_compose') as compose,
            patch.object(
                deploy, 'ready', side_effect=[RuntimeError('health failed'), None]
            ),
        ):
            with self.assertRaises(RuntimeError):
                deploy.deploy_production(value)
            self.assertEqual(
                compose.call_args_list[-1],
                call('admin', 'previous', 'up', '-d', '--no-deps', '--no-build', 'web'),
            )
            self.assertFalse((Path(directory) / 'production-state.json').exists())


if __name__ == '__main__':
    unittest.main()
