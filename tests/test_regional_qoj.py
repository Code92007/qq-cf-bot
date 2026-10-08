import tempfile
import unittest
from pathlib import Path

from qq_cf_bot.core import ChallengeError
from qq_cf_bot.regional import RegionalStore
from qq_cf_bot.regional_qoj import QojPlugin
from qq_cf_bot.storage import SentProblemStore


class QojPluginTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        path=Path(self.tmp.name)/'test.sqlite'
        SentProblemStore(path)
        self.store=RegionalStore(path)
        self.plugin=QojPlugin(self.store)
        self.pid=self.store.aliases['qoj:9726']

    def tearDown(self):
        self.tmp.cleanup()

    def upload(self, token, uid='ucup-team-123', verdict='Accepted', identifier='1234'):
        return self.plugin.upload('Bearer '+token,{'uid':uid,'records':[{
            'id':identifier,'problemId':'9726','submitter':uid,'submittedAt':1720000000,'verdict':verdict}]})

    def test_team_and_personal_identity_are_separate_and_revocable(self):
        team=self.plugin.authorize(1,'ucup-team-123')['token']
        personal=self.plugin.authorize(1,'alice')['token']
        other=self.plugin.authorize(2,'ucup-team-123')['token']
        self.assertEqual(self.upload(team)['matched'],1)
        self.assertTrue(self.store.progress(1)[self.pid]['code'])
        self.assertFalse(self.store.progress(2)[self.pid]['code'])
        with self.assertRaises(ChallengeError):self.upload(team,'alice')
        self.upload(personal,'alice')
        self.plugin.revoke(1,'ucup-team-123')
        with self.assertRaises(ChallengeError):self.upload(team)
        self.upload(other)
        self.assertTrue(self.store.progress(1)[self.pid]['code'])
        self.assertEqual({x['uid'] for x in self.plugin.accounts(1)},{'alice'})
        self.assertNotIn('token',str(self.plugin.accounts(1)))

    def test_reauthorization_invalidates_old_token_and_rejudge_updates(self):
        first=self.plugin.authorize(1,'ucup-team-123')['token']
        self.upload(first,verdict='Wrong Answer')
        self.assertFalse(self.store.progress(1)[self.pid]['code'])
        second=self.plugin.authorize(1,'ucup-team-123')['token']
        with self.assertRaises(ChallengeError):self.upload(first)
        self.upload(second)
        self.upload(second)
        self.assertTrue(self.store.progress(1)[self.pid]['code'])
        self.assertEqual(len(self.store.detail(1,self.pid)['evidence']),1)
        self.upload(second,verdict='100 ✓')
        self.assertTrue(self.store.progress(1)[self.pid]['code'])
        self.upload(second,verdict='100')
        self.assertFalse(self.store.progress(1)[self.pid]['code'])

    def test_sync_and_failed_attempts_preserve_latest_draft(self):
        self.store.save_draft(1,self.pid,'想了一半，稍后证明',0)
        self.store.attempt(1,self.pid,'failed_try_1','oral','想了一半，稍后证明',False,'ORAL_REVIEW','存在反例')
        self.store.save_draft(1,self.pid,'修改边界后，继续证明',1)
        token=self.plugin.authorize(1,'ucup-team-123')['token']
        self.upload(token)
        self.assertEqual(self.store.detail(1,self.pid)['draft']['body'],'修改边界后，继续证明')
        self.assertEqual(len(self.store.detail(1,self.pid)['attempts']),1)
        restarted=RegionalStore(self.store.path)
        self.assertEqual(restarted.detail(1,self.pid)['draft']['version'],2)

    def test_invalid_batch_is_atomic_and_cannot_impersonate(self):
        token=self.plugin.authorize(1,'ucup-team-123')['token']
        payload={'uid':'ucup-team-123','records':[
            {'id':'1234','problemId':'9726','submitter':'ucup-team-123','submittedAt':1720000000,'verdict':'Accepted'},
            {'id':'1235','problemId':'9726','submitter':'someone-else','submittedAt':1720000000,'verdict':'Accepted'}]}
        with self.assertRaises(ValueError):self.plugin.upload('Bearer '+token,payload)
        self.assertFalse(self.store.progress(1)[self.pid]['code'])
        with self.assertRaises(ChallengeError):self.upload('bad-token')
        with self.assertRaises(ValueError):self.plugin.authorize(1,'../../alice')
