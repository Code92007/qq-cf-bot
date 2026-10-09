import unittest
from unittest.mock import patch
from test_webapp import WebApplicationTest, _Handler


class CpcWebTests(unittest.TestCase):
    def setUp(self):
        self.fixture=WebApplicationTest()
        self.fixture.setUp()
        self.app=self.fixture.app
        registration=_Handler({'username':'alice','displayName':'Alice','password':'password123'})
        self.app.handle_post(registration,'/api/auth/register')
        self.cookie=registration.header('Set-Cookie').split(';',1)[0]
        self.csrf=registration.json()['state']['csrfToken']

    def tearDown(self):
        self.fixture.tearDown()

    def test_connect_requires_csrf_and_does_not_expose_token(self):
        denied=_Handler({'token':'private'},cookie=self.cookie)
        self.app.handle_post(denied,'/api/regionals/wall-connect')
        self.assertEqual(denied.status,403)
        wall=self.app.regionals.wall_connection
        authority='fixture-wall'
        snapshot={'schema_version':1,'authority_id':authority,'snapshot_complete':True,
                  'record_count':0,'problems':{},'identity':{'status':'unverified','verified_until':0}}
        with patch.dict('os.environ',{'CPC_OJWALL_URL':'https://wall.invalid','CPC_OJWALL_AUTHORITY_ID':authority}),patch('qq_cf_bot.cpc_integration.fetch',return_value=snapshot):
            linked=_Handler({'token':authority+'.private'},cookie=self.cookie,csrf=self.csrf)
            self.app.handle_post(linked,'/api/regionals/wall-connect')
            self.assertEqual(linked.status,200)
            state=_Handler(cookie=self.cookie)
            self.app.handle_get(state,'/api/regionals')
            self.assertTrue(state.json()['ojWall']['connected'])
            self.assertNotIn('.private',state.wfile.getvalue().decode())
        other=_Handler()
        self.app.handle_get(other,'/api/regionals')
        self.assertEqual(other.status,401)

    def test_malformed_identity_keeps_prior_connection(self):
        wall=self.app.regionals.wall_connection
        valid={'schema_version':1,'authority_id':'fixture','snapshot_complete':True,'record_count':0,
               'problems':{},'identity':{'status':'unverified','verified_until':0}}
        with patch.dict('os.environ',{'CPC_OJWALL_URL':'https://wall.invalid','CPC_OJWALL_AUTHORITY_ID':'fixture'}),patch('qq_cf_bot.cpc_integration.fetch',return_value=valid):
            wall.sync(1,'fixture.private')
        invalid={**valid,'identity':{'status':'approved','verified_until':'invalid'}}
        with patch.dict('os.environ',{'CPC_OJWALL_URL':'https://wall.invalid','CPC_OJWALL_AUTHORITY_ID':'fixture'}),patch('qq_cf_bot.cpc_integration.fetch',return_value=invalid):
            with self.assertRaises(ValueError):wall.sync(1,'fixture.private')
        self.assertTrue(wall.state(1)['connected'])
