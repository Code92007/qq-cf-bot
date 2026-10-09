#!/usr/bin/env python3
"""Contract/flow tests using three disposable databases and real domain logic.

Set CPC_DLUT_CHECKOUT and CPC_WALL_CHECKOUT to test other local checkouts.
External HTTP is replaced at the transport boundary; a separate test exercises
real HTTP handlers on disposable loopback ports.
"""
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import unittest
import uuid
import threading
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from unittest.mock import patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
DLUT = Path(os.environ.get('CPC_DLUT_CHECKOUT', ROOT.parent / 'dlut-cpc'))
WALL = Path(os.environ.get('CPC_WALL_CHECKOUT', ROOT.parent / 'oj-submission-wall'))
sys.path[:0] = [str(ROOT/'src'), str(DLUT), str(WALL)]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


from database import Database
dlut_module = load('cpc_dlut_fixture', DLUT/'cpc_integration.py')
wall_module = load('cpc_wall_fixture', WALL/'cpc_integration.py')
from qq_cf_bot.cpc_integration import WallConnection
from qq_cf_bot.storage import SentProblemStore
from qq_cf_bot.regional import RegionalStore


class FlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.import_dir = tempfile.TemporaryDirectory()
        with patch.dict(os.environ, {'DATA_DIR': cls.import_dir.name}), patch.dict(sys.modules, {'cpc_integration': wall_module}):
            cls.app = load('cpc_wall_app_fixture', WALL/'app.py')

    @classmethod
    def tearDownClass(cls):
        cls.import_dir.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.database = Database(root/'dlut.sqlite')
        self.database.initialize({'meta': {}, 'training': [], 'honors': [{
            'id':'fixture-award','event':'2024 ICPC 杭州站','series':'ICPC','date':'2024-11-01',
            'team':'Fixture team','members':['甲','乙','丙'],'medal':'金牌','rank':'1',
            'source':{'name':'fixture','url':'https://example.com/final'},
        }]})
        self.dlut = dlut_module.Integration(self.database)
        self.app.DATA_DIR = root
        self.app.DB_PATH = root/'wall.sqlite'
        self.app.CACHE_DIR = root/'cache'
        self.app.HTTP_CACHE_DIR = root/'cache/http'
        self.app.init_db()
        with self.app.connect_db() as db:
            for owner in (1,2):
                db.execute('insert into users(id,username,email,display_name,password_hash,created_at) values (?,?,?,?,?,?)', (owner,'user'+str(owner),'e'+str(owner),'User','fixture',1))
        self.wall = wall_module.Integration(self.app)
        self.env = patch.dict(os.environ, {'CPC_DLUT_URL':'https://dlut.invalid','CPC_DLUT_AUTHORITY_ID':self.dlut.authority,'CPC_SYNC_TOKEN':'fixture'})
        self.env.start()
        self.transport = patch.object(wall_module, 'fetch', side_effect=self.fetch_dlut)
        self.transport.start()
        self.wall.sync()
        self.roster = self.dlut.roster()
        self.person = self.roster['members'][0]['id']
        self.participation = self.roster['participations'][0]['id']
        self.cf_path = root/'cf.sqlite'
        SentProblemStore(self.cf_path)
        self.cf = WallConnection(self.cf_path)
        self.regional = RegionalStore(self.cf_path)
        self.regional.wall_connection = self.cf
        self.pid = 'icpc-2024-杭州:A'

    def tearDown(self):
        self.transport.stop();self.env.stop();self.temp.cleanup()

    def fetch_dlut(self, base, path, token, payload=None):
        if payload is not None:
            return self.dlut.submit(payload)
        return self.dlut.roster() if '/roster/' in path else self.dlut.claims(self.wall.authority)

    def approve(self):
        request = self.wall.request_claim('1','user1', {'person':self.person,'note':'队内人工核验'})
        self.dlut.review(request['id'],'approved','fixture-admin')
        self.wall.sync()
        return request['id']

    def evidence(self, accepted=None):
        return {'contest_id':'icpc-2024-杭州','participation_id':self.participation,
                'team':'Fixture team','source_url':'https://example.com/final','source_row':'team-1',
                'accepted':['A'] if accepted is None else accepted,'confirmed':True}

    def fetch_wall(self, base, path, token, payload=None):
        owner = self.wall.token_owner(token)
        if owner is None:
            raise HTTPError(base,401,'revoked',{},None)
        return self.wall.progress(owner)

    def connect_cf(self, token):
        with patch.dict(os.environ, {'CPC_OJWALL_URL':'https://wall.invalid','CPC_OJWALL_AUTHORITY_ID':self.wall.authority}), patch('qq_cf_bot.cpc_integration.fetch', side_effect=self.fetch_wall):
            self.cf.sync(1,token)

    def test_full_flow_oral_stays_local_and_members_do_not_leak(self):
        self.approve();self.wall.import_onsite(self.evidence())
        self.assertTrue(self.wall.progress('1')['problems'][self.pid]['onsite'])
        self.assertNotIn(self.pid,self.wall.progress('2')['problems'])
        token=self.wall.issue_token('1')['token'];self.connect_cf(token)
        self.regional.attempt(1,self.pid,'fixture-oral','oral','思路',True,'ORAL_ACCEPTED','通过')
        progress=self.regional.progress(1)[self.pid]
        self.assertTrue(progress['oral']);self.assertTrue(progress['onsite']);self.assertFalse(progress['code'])
        self.assertNotIn('oral',self.wall.progress('1')['problems'][self.pid])
        self.cf.disconnect(1)
        self.assertTrue(self.regional.progress(1)[self.pid]['oral'])
        self.assertFalse(self.regional.progress(1)[self.pid]['onsite'])

    def test_claim_and_scoreboard_revocations_replace_previous_ac(self):
        claim=self.approve();key=self.wall.import_onsite(self.evidence())
        self.wall.import_onsite(self.evidence([]))
        self.assertNotIn(self.pid,self.wall.progress('1')['problems'])
        self.wall.import_onsite(self.evidence())
        self.wall.revoke_onsite(key)
        self.assertNotIn(self.pid,self.wall.progress('1')['problems'])
        self.wall.import_onsite(self.evidence())
        self.dlut.review(claim,'revoked','fixture-admin');self.wall.sync()
        self.assertNotIn(self.pid,self.wall.progress('1')['problems'])

    def test_starred_onsite_ac_reaches_both_services_without_personal_submission(self):
        with self.database.connect() as db:
            db.execute("update honors set official=0,medal='' where id='fixture-award'")
        self.wall.sync()
        with self.wall.db() as db:
            remote, _ = self.wall.remote(db)
        self.assertFalse(remote['roster']['participations'][0]['official'])
        self.approve()
        self.wall.import_onsite(self.evidence())
        progress = self.wall.progress('1')['problems'][self.pid]
        self.assertTrue(progress['onsite'])
        self.assertFalse(progress['personal'])
        self.assertFalse(progress['team'])
        self.connect_cf(self.wall.issue_token('1')['token'])
        self.assertTrue(self.regional.progress(1)[self.pid]['onsite'])
        self.assertFalse(self.regional.progress(1)[self.pid]['code'])
        with self.app.connect_db() as db:
            self.assertEqual(db.execute('select count(*) from submissions').fetchone()[0], 0)

    def test_team_online_is_separate_and_real_ac_is_preserved(self):
        with self.app.connect_db() as db:
            db.execute("insert into handles(owner_type,owner_id,platform,handle,created_at) values ('user','1','qoj','ucup-team-fixture',1)")
            db.execute("insert into submissions(owner_type,owner_id,platform,handle,remote_id,problem_id,verdict,submitted_at,created_at) values ('user','1','qoj','ucup-team-fixture','123','9726','AC',1,1)")
        p=self.wall.progress('1')['problems'][self.pid]
        self.assertTrue(p['team']);self.assertFalse(p['personal'])
        self.connect_cf(self.wall.issue_token('1')['token'])
        self.assertTrue(self.regional.progress(1)[self.pid]['code'])

    def test_approval_triggers_profile_import_merge_retry_and_rejudge(self):
        with self.database.connect() as db:
            local = db.execute("select local_id from cpc_ids where kind='person' and uid=?",(self.person,)).fetchone()[0]
            db.execute("insert into member_identities(provider,external_id,member_id) values ('cpcfinder',?,?)",(str(uuid.uuid4()),local))
        claim=self.wall.request_claim('1','user1',{'person':self.person,'note':'fixture'})
        self.wall.sync()
        award={'contestId':62,'contestName':'Fixture contest','teamName':'Fixture team','date':'2024-11-01'}
        body={**self.evidence(),'cpcfinder_contest_id':62,'contest_name':'Fixture contest','contest_date':'2024-11-01',
              'problem_labels':[p['index'] for p in self.wall.contests['icpc-2024-杭州']['problems']]}
        with patch.object(wall_module,'profile_awards',return_value=[award]) as profiles, patch.object(wall_module,'Scoreboards') as boards:
            boards.return_value.prepare.return_value=body
            self.wall.sync_onsite()
            profiles.assert_not_called()
            self.dlut.review(claim['id'],'approved','admin');self.wall.sync()
            with self.app.connect_db() as db:
                db.execute("insert into handles(owner_type,owner_id,platform,handle,created_at) values ('user','1','codeforces','fixture',1)")
                for problem in ['105657A','105657B']:
                    db.execute("insert into submissions(owner_type,owner_id,platform,handle,remote_id,problem_id,verdict,submitted_at,created_at) values ('user','1','codeforces','fixture',?,?, 'AC',1,1)",(problem,problem))
            self.wall.sync_onsite()
            progress=self.wall.progress('1')
            self.assertEqual(progress['onsite_sync']['status'],'complete')
            self.assertTrue(progress['problems'][self.pid]['personal'])
            self.assertTrue(progress['problems'][self.pid]['onsite'])
            self.assertEqual(sum(p['personal'] or p['onsite'] for p in progress['problems'].values()),2)
            self.assertFalse(self.wall.progress('2')['onsite_contests'])
            self.wall.sync_onsite(force=True)
            with self.wall.db() as db:self.assertEqual(db.execute('select count(*) from cpc_onsite_history').fetchone()[0],1)
            boards.return_value.prepare.side_effect=ValueError('upstream unavailable')
            self.wall.sync_onsite(force=True)
            self.assertEqual(self.wall.progress('1')['onsite_sync']['status'],'partial')
            self.assertTrue(self.wall.progress('1')['problems'][self.pid]['onsite'])
            boards.return_value.prepare.side_effect=None
            boards.return_value.prepare.return_value={**body,'accepted':[]}
            self.wall.sync_onsite(force=True)
            self.assertFalse(self.wall.progress('1')['problems'][self.pid]['onsite'])
            self.assertTrue(self.wall.progress('1')['problems'][self.pid]['personal'])
            self.dlut.review(claim['id'],'revoked','admin');self.wall.sync()
            self.assertFalse(self.wall.progress('1')['onsite_contests'])

    def test_profile_import_retains_contests_outside_current_problem_catalog(self):
        self.approve()
        body={**self.evidence(),'contest_id':'cpcfinder-62','cpcfinder_contest_id':62,
              'contest_name':'Older profile contest','contest_date':'2024-11-01','problem_labels':['A','B']}
        self.wall.import_auto_onsite(body)
        progress=self.wall.progress('1')
        self.assertTrue(progress['problems']['cpcfinder-62:A']['onsite'])
        self.assertFalse(progress['onsite_contests'][0]['mapped'])
        self.assertEqual(progress['unmapped_count'],1)
        self.connect_cf(self.wall.issue_token('1')['token'])
        with self.cf.db() as db:
            raw=json.loads(db.execute('select body from cpc_wall_links where user_id=1').fetchone()[0])
        self.assertTrue(raw['problems']['cpcfinder-62:A']['onsite'])

    def test_legacy_board_without_cpcfinder_profile_is_imported_and_merged(self):
        self.approve()
        body={**self.evidence(),'contest_id':'rankland-legacy','contest_name':'Legacy contest',
              'contest_date':'2024-11-01','problem_labels':['A','B'],
              'reference_urls':['https://codeforces.com/gym/100001']}
        with self.app.connect_db() as db:
            db.execute("insert into handles(owner_type,owner_id,platform,handle,created_at) values ('user','1','codeforces','fixture',1)")
            db.execute("insert into submissions(owner_type,owner_id,platform,handle,remote_id,problem_id,verdict,submitted_at,created_at) values ('user','1','codeforces','fixture','1','100001A','AC',1,1)")
        with patch.object(wall_module,'profile_awards') as profiles, patch.object(wall_module,'Scoreboards') as boards:
            boards.return_value.prepare.return_value=body
            self.wall.sync_onsite()
            profiles.assert_not_called()
        progress=self.wall.progress('1')
        self.assertEqual(progress['onsite_sync']['status'],'complete')
        self.assertEqual(len(progress['problems']),1)
        self.assertTrue(progress['problems']['rankland-legacy:A']['personal'])
        self.assertTrue(progress['problems']['rankland-legacy:A']['onsite'])
        self.assertFalse(self.wall.progress('2')['onsite_contests'])

    def test_bad_snapshot_and_wrong_authority_preserve_cache(self):
        self.approve();self.wall.import_onsite(self.evidence())
        token=self.wall.issue_token('1')['token'];self.connect_cf(token)
        before=self.cf.state(1)['lastSync']
        with patch.dict(os.environ,{'CPC_OJWALL_URL':'https://wall.invalid','CPC_OJWALL_AUTHORITY_ID':self.wall.authority}), patch('qq_cf_bot.cpc_integration.fetch',return_value={'authority_id':self.wall.authority,'schema_version':1,'snapshot_complete':False}):
            with self.assertRaises(ValueError):self.cf.sync(1,token)
        self.assertEqual(self.cf.state(1)['lastSync'],before)
        self.assertTrue(self.regional.progress(1)[self.pid]['onsite'])
        with patch.object(wall_module,'fetch',return_value={'authority_id':str(uuid.uuid4()),'schema_version':1,'snapshot_complete':True}):
            with self.assertRaises(ValueError):self.wall.sync()
        self.assertTrue(self.wall.progress('1')['problems'][self.pid]['onsite'])

    def test_incomplete_roster_pair_keeps_valid_onsite_evidence(self):
        self.approve();self.wall.import_onsite(self.evidence())
        roster=self.dlut.roster()
        claims=self.dlut.claims(self.wall.authority)
        for bad_roster,bad_claims in [
            ({**roster,'record_count':0},claims),
            (roster,{**claims,'client_id':str(uuid.uuid4())}),
            (roster,{**claims,'claims':[{k:v for k,v in claims['claims'][0].items() if k!='updated'}]}),
        ]:
            with patch.object(wall_module,'fetch',side_effect=[bad_roster,bad_claims]):
                with self.assertRaises((ValueError,KeyError)):self.wall.sync()
            self.assertTrue(self.wall.progress('1')['problems'][self.pid]['onsite'])

    def test_bundled_catalog_and_wire_helpers_match(self):
        self.assertEqual((ROOT/'src/qq_cf_bot/catalog/regionals.json').read_bytes(),(WALL/'catalog/regionals.json').read_bytes())
        common=(ROOT/'src/qq_cf_bot/cpc_common.py').read_bytes()
        self.assertEqual(common,(WALL/'cpc_common.py').read_bytes())
        self.assertEqual(common,(DLUT/'cpc_common.py').read_bytes())

    def test_token_rotation_cannot_read_other_user_or_keep_old_grant(self):
        old=self.wall.issue_token('1')['token'];new=self.wall.issue_token('1')['token']
        self.assertIsNone(self.wall.token_owner(old));self.assertEqual(self.wall.token_owner(new),'1')
        self.assertEqual(self.wall.token_owner(self.wall.issue_token('2')['token']),'2')
        self.connect_cf(new)
        self.wall.issue_token('1')
        with patch.dict(os.environ,{'CPC_OJWALL_URL':'https://wall.invalid','CPC_OJWALL_AUTHORITY_ID':self.wall.authority}), patch('qq_cf_bot.cpc_integration.fetch',side_effect=self.fetch_wall):
            with self.assertRaises(ValueError):self.cf.sync(1)
        self.assertFalse(self.cf.state(1)['connected'])

    def test_copy_all_three_databases_preserves_ids_and_links(self):
        self.approve();self.wall.import_onsite(self.evidence())
        token=self.wall.issue_token('1')['token'];self.connect_cf(token)
        destination=Path(self.temp.name)/'moved';destination.mkdir()
        for name,source in [('dlut',self.database.path),('wall',self.app.DB_PATH),('cf',self.cf_path)]:
            with sqlite3.connect(source) as src,sqlite3.connect(destination/(name+'.sqlite')) as dst:
                src.backup(dst)
        restored=dlut_module.Integration(Database(destination/'dlut.sqlite'))
        self.assertEqual(restored.authority,self.dlut.authority)
        self.assertEqual(restored.roster(),self.roster)
        self.app.DB_PATH=destination/'wall.sqlite'
        wall=wall_module.Integration(self.app)
        self.assertEqual(wall.authority,self.wall.authority);self.assertEqual(wall.token_owner(token),'1')
        restored_cf=WallConnection(destination/'cf.sqlite')
        self.assertEqual(restored_cf.authority,self.cf.authority)
        store=RegionalStore(destination/'cf.sqlite');store.wall_connection=restored_cf
        self.assertTrue(store.progress(1)[self.pid]['onsite'])

    def test_expired_identity_does_not_propagate_by_refreshing_wall(self):
        self.approve();self.wall.import_onsite(self.evidence())
        with self.wall.db() as db:db.execute('update cpc_remote set checked=?',(int(time.time())-86401,))
        self.connect_cf(self.wall.issue_token('1')['token'])
        self.assertFalse(self.regional.progress(1)[self.pid]['onsite'])

    def test_real_http_authentication_and_service_routes(self):
        with patch.dict(sys.modules, {'cpc_integration': dlut_module}):
            dlut_app=load('cpc_dlut_http_fixture',DLUT/'app.py')
        dlut_app.DATABASE_PATH=self.database.path
        servers=[]
        try:
            for handler in (dlut_app.SiteHandler,self.app.AppHandler):
                server=ThreadingHTTPServer(('127.0.0.1',0),handler)
                servers.append(server)
                threading.Thread(target=server.serve_forever,daemon=True).start()
            dlut_url='http://127.0.0.1:'+str(servers[0].server_port)
            wall_url='http://127.0.0.1:'+str(servers[1].server_port)
            self.app._cpc_service=self.wall
            from cpc_common import fetch as actual_fetch
            self.assertEqual(actual_fetch(dlut_url,'/api/integration/v1/roster/snapshot','fixture')['authority_id'],self.dlut.authority)
            with self.assertRaises(HTTPError) as denied:
                actual_fetch(dlut_url,'/api/integration/v1/roster/snapshot','wrong')
            self.assertEqual(denied.exception.code,403)
            with self.app.connect_db() as db:
                session=self.app.create_session(db,'user','1',1)
            headers={'Cookie':'ojwall_session='+session,'Origin':wall_url,'Content-Type':'application/json'}
            request=Request(wall_url+'/api/cpc/token',data=b'{}',headers=headers)
            with urlopen(request,timeout=5) as response:token=json.load(response)['token']
            self.assertEqual(actual_fetch(wall_url,'/api/integration/v1/me/progress/snapshot',token)['subject_id'],self.wall.progress('1')['subject_id'])
            with urlopen(wall_url+'/regionals',timeout=5) as response:
                self.assertIn('区域赛进度',response.read().decode())
            request=Request(wall_url+'/api/cpc/token',data=b'{}',headers={**headers,'Origin':'https://other.example'})
            with self.assertRaises(HTTPError) as denied:urlopen(request,timeout=5)
            self.assertEqual(denied.exception.code,403)
        finally:
            self.app._cpc_service=None
            for server in servers:
                server.shutdown();server.server_close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
