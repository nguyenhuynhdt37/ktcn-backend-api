import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('deploy', Path(__file__).with_name('deploy.py'))
deploy=importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class DeploymentTests(unittest.TestCase):
    def request(self):
        image='ghcr.io/nguyenhuynhdt37/ktcn-backend-api@sha256:'+'a'*64
        return dict(action='stage',component='backend',commit='b'*40,staging=image,production=image)

    def test_staging_request(self):
        deploy.validate_request(self.request(),'stage-backend')

    def test_staging_key_cannot_promote(self):
        request=self.request(); request['action']='promote'
        with self.assertRaises(ValueError): deploy.validate_request(request,'stage-backend')

    def test_component_key_cannot_deploy_other_component(self):
        with self.assertRaises(ValueError): deploy.validate_request(self.request(),'stage-admin')

    def test_mutable_tags_and_foreign_images_rejected(self):
        for image in ['ghcr.io/nguyenhuynhdt37/ktcn-backend-api:latest',
                      'ghcr.io/attacker/backend@sha256:'+'a'*64,
                      'ghcr.io/nguyenhuynhdt37/ktcn-admin-portal@sha256:'+'a'*64]:
            with self.subTest(image=image),self.assertRaises(ValueError):
                deploy.validate_image('backend',image)

    def test_shell_and_path_injection_rejected(self):
        for release in ['../../etc/passwd','$(touch /tmp/bad)','20261107180000-abc;exit']:
            with self.subTest(release=release),self.assertRaises(ValueError):
                deploy.validate_request(dict(action='promote',release=release),'production')

    def test_partial_release_rejected(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(deploy,'ROOT',Path(directory)):
            deploy.save(Path(directory)/'releases'/'20261107180000-aaaaaaaaaaaa.json',{'components':{'backend':self.request()}})
            with self.assertRaises(ValueError): deploy.get_release('20261107180000-aaaaaaaaaaaa')

    def test_changed_candidate_cannot_be_promoted(self):
        data={'components':{c:{'production':'image'} for c in deploy.COMPONENTS}}
        with patch.object(deploy,'get_release',return_value=data),patch.object(deploy,'load',return_value={'release':'another'}),patch.object(deploy,'run') as run:
            with self.assertRaises(ValueError): deploy.production(dict(action='promote',release='20261107180000-aaaaaaaaaaaa'))
            run.assert_not_called()

    def test_rollback_requires_previously_deployed_release(self):
        data={'components':{c:{'production':'image'} for c in deploy.COMPONENTS}}
        with patch.object(deploy,'get_release',return_value=data),patch.object(deploy,'load',return_value=[]),patch.object(deploy,'run') as run:
            with self.assertRaises(ValueError): deploy.production(dict(action='rollback',release='20261107180000-aaaaaaaaaaaa'))
            run.assert_not_called()

    def test_failed_test_invalidates_review_candidate(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(deploy,'ROOT',Path(directory)),patch.object(deploy,'run',side_effect=RuntimeError('pull failed')):
            candidate=Path(directory)/'candidate.json'; deploy.save(candidate,{'release':'previous'})
            with self.assertRaises(RuntimeError): deploy.stage(self.request())
            self.assertFalse(candidate.exists())


if __name__ == '__main__': unittest.main()
