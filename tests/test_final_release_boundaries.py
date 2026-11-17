"""Independent regression gates for rc2 security, evidence and first-user integrity.

Tests originate from Muse's nine live failures. No test is allowed to weaken
receiver authority just to make a previously failing UI succeed.
"""
from __future__ import annotations
import json, tempfile, threading, unittest, urllib.request, urllib.error
from pathlib import Path
from genie_server import start_genie_server
from openline_009_living_project import LivingProjectEngine
import genie_server


class TestFinalReleaseBoundaries(unittest.TestCase):
    def setUp(self):
        self.state = Path(tempfile.mkdtemp(prefix="genie-release-falsifier-"))
        self.server = start_genie_server(port=0, state_dir=self.state)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_port

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def request(self, path, *, host=None, method="GET", body=None):
        headers = {"Host":host or f"127.0.0.1:{self.port}"}
        data = None
        if method == "POST":
            headers["Content-Type"]="application/json"
            data=json.dumps(body or {}).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}",
                                     data=data,method=method,headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=15) as res:
                return res.status, res.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def test_01_bound_server_and_host_across_all_routes(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        for path in ("/", "/products", "/api/status", "/api/semantic/state", "/neighborhood"):
            code, _ = self.request(path, host="attacker.example")
            self.assertEqual(code,403,(path,code))
            code, _ = self.request(path, host=f"localhost:{self.port+1}")
            self.assertEqual(code,403,(path,code))
        code,_ = self.request('/api/status')
        self.assertEqual(code,200)

    def test_02_server_owned_neighborhood_identity(self):
        body = {"workspace_key":"board", "payload":{
            "requester_role":"board","requester_unit_id":"BOARD-OAK-CREEK",
            "board_authorized":True, "human_approved":True}}
        self.assertEqual(self.request('/api/neighborhood/stage',method='POST',body=body)[0],403)
        self.assertEqual(self.request('/api/neighborhood/action',method='POST',body={
            **body,"action":"authorize_action_packet"})[0],403)
        self.assertEqual(self.request('/api/neighborhood/dossier?workspace=board')[0],403)
        self.assertEqual(self.request('/api/export?project_id=neighborhood-board-oak-creek')[0],403)
        self.assertEqual(self.request('/api/project?project_id=neighborhood-board-oak-creek')[0],403)
        self.assertEqual(self.request('/api/import',method='POST',body={
            "portable_bundle":{"project_id":"neighborhood-board-oak-creek"}})[0],403)

    def test_03_semantic_miss_is_not_compute(self):
        old = genie_server.HERE
        try:
            genie_server.HERE = Path(tempfile.mkdtemp(prefix="semantic-cache-miss-"))
            code,raw=self.request('/api/semantic/state')
            self.assertEqual(code,503)
            self.assertIn(b'not_precomputed',raw)
        finally:
            genie_server.HERE=old

    def test_04_stop_and_resume_before_bootstrap(self):
        code,stop_raw=self.request('/api/stop',method='POST')
        self.assertEqual(code,200)
        acknowledged_epoch=json.loads(stop_raw)['new_epoch']
        code,raw=self.request('/api/status')
        self.assertEqual(code,200)
        self.assertTrue(json.loads(raw).get('stopped'))
        code,_=self.request('/api/clear_stop',method='POST',body={'expected_epoch':acknowledged_epoch})
        self.assertEqual(code,200)
        code,raw=self.request('/api/status')
        self.assertFalse(json.loads(raw).get('stopped'))

    def test_05_assumption_change_reopens_and_external_revocation_blocks_review(self):
        eng=self.server.genie_engine
        eng.ensure_five_products_initialized()
        pid=eng.FIVE_PRODUCT_SPECS['energy']['project_id']
        proposal=eng.stage_five_product_proposal('energy', {'inputs':{'households':43}})['proposal']
        eng.accept_exploratory_change(pid,proposal['proposal_id'])
        current=eng.get_project_bundle(pid)['accepted']
        self.assertEqual(eng.recall_ledger.standing(pid+':scenario_plan',now=260).status,'REOPEN')
        with self.assertRaisesRegex(PermissionError,'STALE_REOPEN_REQUIRED'):
            eng.execute_five_product_action('energy','authorize_procurement',{'human_approved':True})
        with self.assertRaisesRegex(PermissionError,'sha_mismatch'):
            eng.confirm_five_product_local_basis_review('energy',expected_accepted_sha256='bad',human_reviewed=True)
        result=eng.confirm_five_product_local_basis_review('energy',
                    expected_accepted_sha256=current['state_sha256'],human_reviewed=True)
        self.assertEqual(result['dnf_standing'],'CURRENT')
        eng.recall_living_project_dependency(pid,'workflow','independent_upstream_revocation')
        with self.assertRaisesRegex(PermissionError,'unrelated_or_unproven'):
            eng.confirm_five_product_local_basis_review('energy',
                    expected_accepted_sha256=current['state_sha256'],human_reviewed=True)

    def test_06_static_user_and_portability_boundary(self):
        here=Path(__file__).resolve().parent.parent
        ui=(here/'openline_five_products.html').read_text()
        neigh=(here/'openline_neighborhood.html').read_text()
        self.assertIn('Review Updated Assumptions',ui)
        self.assertIn('expected_base_sha256',ui)
        self.assertIn('Preparing your five project examples',ui)
        self.assertNotIn('Be Neighborly',neigh)
        self.assertNotIn('board_authorized=1',neigh)
        for name in ('run_civilization_frontier_001.py', 'run_final_closure_001.py',
                     'run_human_planetary_benefit_loop_001.py','run_neighborhood_001.py',
                     'run_010_verified_succession.py'):
            self.assertNotIn('/working_dir/',(here/name).read_text())

if __name__=='__main__':unittest.main()
