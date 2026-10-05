import http.client
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from unittest.mock import Mock
from types import SimpleNamespace
import numpy as np
from lens.feed.bridge import Companion, make_handler, paper_id
from lens.feed.rank import Profile


class BridgeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.c = Companion(root/'profile', root/'cache')
        self.paper = {'id':'2207.01848', 'title':'TabPFN', 'abstract':'A test fixture.',
                      'authors':['A'], 'categories':['cs.LG'], 'primary':'cs.LG',
                      'created':'2022-07-05', 'url':'https://arxiv.org/abs/2207.01848'}
        (self.c.store.root/'pool-test.json').write_text(json.dumps([self.paper]))
        self.server = ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.c,Path('extension')))
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.temp.cleanup()
    def request(self,path,body=None,auth=True,headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        hdr = {'Authorization':'Bearer '+self.c.token} if auth else {}
        hdr.update(headers or {})
        conn.request('GET' if body is None else 'POST',path,body=None if body is None else json.dumps(body),headers=hdr)
        r=conn.getresponse(); data=r.read(); conn.close()
        return r.status,json.loads(data)
    def test_requires_key(self):
        self.assertEqual(self.request('/api/status',auth=False)[0],401)
    def test_access_setup_is_authenticated_and_never_returns_the_token(self):
        self.c.tabpfn_token_path=self.c.cache/'test-provider/auth_token'
        token='test-access-token-for-unit-tests-only'
        self.assertEqual(self.request('/api/tabpfn-access',{'token':token},auth=False)[0],401)
        with patch('lens.feed.access._verify',return_value=True),patch.dict(os.environ,{}):
            code,data=self.request('/api/tabpfn-access',{'token':token})
            self.assertEqual(code,200);self.assertTrue(data['tabpfn_configured'])
            self.assertNotIn(token,json.dumps(data))
            self.assertEqual(self.c.tabpfn_token_path.stat().st_mode&0o777,0o600)
        self.assertEqual(self.c.status()['likes'],0)
    def test_blocks_foreign_origin_and_rebinding(self):
        self.assertEqual(self.request('/api/status',headers={'Origin':'https://evil.example'})[0],403)
        self.assertEqual(self.request('/api/status',headers={'Host':'evil.example'})[0],403)
    def test_pair_key_only_same_origin_browser(self):
        self.assertEqual(self.request('/api/session',auth=False)[0],403)
        self.assertEqual(self.request('/api/session',auth=False,headers={'Sec-Fetch-Site':'cross-site'})[0],403)
        code,data=self.request('/api/session',auth=False,headers={'Sec-Fetch-Site':'same-origin'})
        self.assertEqual(code,200); self.assertEqual(data['token'],self.c.token)
    def test_rating_roundtrip_and_empty_candidates(self):
        code,data=self.request('/api/rate',{'id':self.paper['id'],'rating':1})
        self.assertEqual(code,200); self.assertEqual(data['likes'],1)
        self.assertEqual(self.request('/api/shortlist')[1]['papers'],[])
        self.assertEqual(self.request('/api/library')[1]['papers'][0]['rating'],1)
        self.request('/api/rate',{'id':self.paper['id'],'rating':-1})
        self.assertEqual(self.request('/api/status')[1]['dislikes'],1)
        self.request('/api/rate',{'id':self.paper['id'],'rating':0})
        self.assertEqual(self.request('/api/library')[1]['papers'],[])
    def test_rate_paper_outside_pool(self):
        other={**self.paper,'id':'1706.03762','title':'Attention Is All You Need'}
        with patch('lens.feed.bridge.fetch_paper',return_value=other) as fetch:
            code,data=self.request('/api/rate',{'id':other['id'],'rating':1})
        self.assertEqual(code,200)
        self.assertEqual(data['likes'],1)
        fetch.assert_called_once_with(other['id'],self.c.cache/'arxiv')
        self.assertEqual(self.request('/api/library')[1]['papers'][0]['id'],other['id'])
    def test_cited_paper_lookup_uses_canonical_metadata(self):
        code,data=self.request('/api/paper?id=2207.01848')
        self.assertEqual(code,200)
        self.assertEqual(data['title'],self.paper['title'])
        other={**self.paper,'id':'1706.03762','title':'Attention Is All You Need'}
        with patch('lens.feed.bridge.fetch_paper',return_value=other) as fetch:
            code,data=self.request('/api/paper?id=1706.03762')
        self.assertEqual(code,200)
        self.assertEqual(data['id'],other['id'])
        fetch.assert_called_once_with(other['id'],self.c.cache/'arxiv')
        self.assertEqual(self.request('/api/paper?id=../../file')[0],400)
        self.assertEqual(self.request('/api/paper?id=2207.01848',auth=False)[0],401)
    def test_reference_resolution_auth_validation_and_canonical_title_guard(self):
        details={'doi':'10.1234/example','title':'An expected paper title','reference':'A public bibliography reference.'}
        result={'state':'resolved','candidates':[{'id':self.paper['id'],'title':'A completely unrelated paper title'}],'warning':''}
        self.assertEqual(self.request('/api/resolve-reference',details,auth=False)[0],401)
        self.assertEqual(self.request('/api/resolve-reference',{'doi':'bad-doi'})[0],400)
        with patch('lens.feed.bridge.resolve',return_value=result):
            code,data=self.request('/api/resolve-reference',details)
        self.assertEqual(code,200);self.assertEqual(data['state'],'unresolved')
        self.assertEqual(data['candidates'],[])
        with patch('lens.feed.bridge.resolve',side_effect=RuntimeError('Provider unavailable')):
            code,data=self.request('/api/resolve-reference',details)
        self.assertEqual(code,200);self.assertEqual(data['state'],'unavailable')
        self.assertEqual(self.c.status()['likes'],0)

    def test_reference_resolution_automatically_uses_next_valid_version(self):
        wrong={**self.paper,'id':'1706.03762','title':'Incorrect mapped title'}
        result={'state':'resolved','candidates':[wrong,self.paper],'warning':'Found the closest arXiv version.'}
        with patch('lens.feed.bridge.resolve',return_value=result),patch.object(self.c,'paper',side_effect=[{**wrong,'title':'Unrelated canonical paper'},self.paper]):
            code,data=self.request('/api/resolve-reference',{'title':self.paper['title']})
        self.assertEqual(code,200);self.assertEqual(data['state'],'resolved')
        self.assertEqual(data['candidates'],[self.paper])
        self.assertEqual(self.c.status()['likes'],0)

    def test_doi_deposit_metadata_is_reused_for_hover_scoring_and_after_restart(self):
        paper={**self.paper,'id':'1810.04805','title':'BERT','source':'datacite','doi_match':False}
        result={'state':'resolved','candidates':[paper],'warning':'Found the closest arXiv version.'}
        with patch('lens.feed.bridge.resolve',return_value=result),patch('lens.feed.bridge.fetch_paper') as fetch:
            code,data=self.request('/api/resolve-reference',{'title':'BERT','reference':'BERT reference.'})
            self.assertEqual(code,200);self.assertEqual(data['state'],'resolved')
            self.assertEqual(self.request('/api/paper?id=1810.04805')[1]['title'],'BERT')
            self.assertEqual(self.request('/api/paper-match?id=1810.04805')[1]['id'],'1810.04805')
            restarted=Companion(self.c.store.root,self.c.cache)
            self.assertEqual(restarted.paper('1810.04805')['abstract'],paper['abstract'])
            fetch.assert_not_called()
        self.assertEqual(self.c.status()['likes'],0)

    def test_cached_arxiv_metadata_resolves_locally_without_provider_requests(self):
        folder=self.c.cache/'arxiv';folder.mkdir(parents=True)
        (folder/'abs-1810.04805.html').write_text('<meta name="citation_arxiv_id" content="1810.04805"><meta name="citation_title" content="BERT"><meta name="citation_abstract" content="An abstract."><meta name="citation_author" content="Jacob Devlin"><meta name="citation_date" content="2018/10/11">')
        restarted=Companion(self.c.store.root,self.c.cache)
        with patch('lens.feed.references._get') as get,patch('lens.feed.references._datacite') as fallback:
            result=restarted.resolve_reference({'title':'BERT','reference':'BERT reference.'})
        self.assertEqual(result['state'],'resolved');self.assertEqual(result['candidates'][0]['id'],'1810.04805')
        get.assert_not_called();fallback.assert_not_called()

    def test_library_orders_likes_and_dislikes_by_rating_time(self):
        other={**self.paper,'id':'1706.03762'}
        (self.c.store.root/'pool-test.json').write_text(json.dumps([self.paper,other]))
        self.request('/api/rate',{'id':self.paper['id'],'rating':1})
        self.request('/api/rate',{'id':other['id'],'rating':-1})
        papers=self.request('/api/library')[1]['papers']
        self.assertEqual([p['id'] for p in papers],[other['id'],self.paper['id']])
        self.assertTrue(all(p.get('rated_at_time') for p in papers))
    def test_no_profile_is_labeled_recent(self):
        code,data=self.request('/api/shortlist?category=cs.LG')
        self.assertEqual(code,200); self.assertEqual(data['engine'],'recent')
        self.assertFalse(data['personalized']); self.assertIsNone(data['papers'][0]['match'])
    def test_validation(self):
        self.assertEqual(self.request('/api/rate',{'id':'../../file','rating':1})[0],400)
        self.assertEqual(self.request('/api/rate',{'id':'2207.01848','rating':True})[0],400)
        self.assertEqual(self.request('/api/interests',{'interests':'x'*2001})[0],400)
        self.assertEqual(paper_id('hep-th/9901001v2'),'hep-th/9901001')
    def test_interests_persist(self):
        self.request('/api/interests',{'interests':'  retrieval  '})
        self.assertEqual(self.request('/api/status')[1]['interests'],'retrieval')
    def test_readiness_uses_updated_ranker_thresholds(self):
        papers=[{**self.paper,'id':f'2401.{i:05d}'} for i in range(30)]
        self.c.store.save_profile(Profile(likes=papers[:26],dislikes=papers[26:29]))
        code,data=self.request('/api/status')
        self.assertEqual(code,200)
        self.assertEqual((data['match_after'],data['need_ratings']), (30,1))
        self.assertEqual((data['need_likes'],data['need_dislikes']), (0,0))
        self.c.store.save_profile(Profile(likes=papers))
        data=self.request('/api/status')[1]
        self.assertEqual((data['need_ratings'],data['need_dislikes']), (3,3))
        self.c.store.save_profile(Profile(likes=papers[:27],dislikes=papers[27:]))
        self.assertEqual(self.request('/api/status')[1]['need_ratings'],0)
    def test_citation_match_requires_access_and_enough_other_ratings(self):
        with patch('lens.feed.bridge.Embedder') as embedder:
            code,data=self.request('/api/paper-match?id=2207.01848')
        self.assertEqual(code,200)
        self.assertIsNone(data['match'])
        embedder.assert_not_called()
        self.assertEqual(self.request('/api/paper-match?id=2207.01848',auth=False)[0],401)
        self.assertEqual(self.request('/api/paper-match?id=../../file')[0],400)
    def test_citation_match_excludes_own_rating_caches_for_five_changes(self):
        papers=[{**self.paper,'id':f'2401.{i:05d}'} for i in range(30)]
        self.c.store.save_profile(Profile(likes=papers[:27]+[self.paper],dislikes=papers[27:]))
        ranker=Mock()
        ranker.ready.return_value=0
        ranker.rank.return_value=SimpleNamespace(match=np.array([.73]))
        self.c.rankers['tabpfn-fast']=ranker
        self.c.embedder=Mock()
        self.c.embedder.papers.side_effect=lambda rows:np.ones((len(rows),2),dtype=np.float32)
        with patch.dict('os.environ',{'TABPFN_TOKEN':'test-credential'}):
            code,data=self.request('/api/paper-match?id=2207.01848')
            self.assertEqual((code,data['rating'],data['match']),(200,1,.73))
            context=ranker.rank.call_args.args[2]
            self.assertNotIn(self.paper['id'],[p['id'] for p in context.labeled])
            self.request('/api/paper-match?id=2207.01848')
            self.assertEqual(ranker.rank.call_count,1)
            initial=self.c.status()['citation_revision']
            self.request('/api/rate',{'id':self.paper['id'],'rating':-1})
            refreshed=self.request('/api/paper-match?id=2207.01848')[1]
            self.assertEqual(refreshed['rating'],-1)
            self.assertEqual(ranker.rank.call_count,1)
            for i in range(4):
                self.request('/api/rate',{'id':papers[i]['id'],'rating':-1})
                self.request('/api/paper-match?id=2207.01848')
                self.assertEqual(ranker.rank.call_count,1 if i<3 else 2)
            self.assertEqual(self.c.status()['citation_revision'],initial+1)
            self.assertEqual(self.c.status()['citation_changes'],0)
    def test_citation_snapshot_stays_consistent_and_resets_for_interests_or_external_edits(self):
        papers=[{**self.paper,'id':f'2401.{i:05d}'} for i in range(32)]
        self.c.store.save_profile(Profile(likes=papers[:27],dislikes=papers[27:30]))
        ranker=Mock();ranker.ready.return_value=0
        ranker.rank.return_value=SimpleNamespace(match=np.array([.73]))
        self.c.rankers['tabpfn-fast']=ranker
        self.c.embedder=Mock();self.c.embedder.papers.side_effect=lambda rows:np.ones((len(rows),2))
        with patch.dict('os.environ',{'TABPFN_TOKEN':'test-credential'}):
            self.c.paper_match(self.paper['id'])
            self.c.update_rating({'id':papers[0]['id'],'rating':-1})
            with patch('lens.feed.bridge.fetch_paper',return_value=papers[30]):
                self.c.paper_match(papers[30]['id'])
            snapshot=ranker.rank.call_args.args[2]
            self.assertEqual([p['id'] for p in snapshot.likes],[p['id'] for p in papers[:27]])
            revision=self.c.status()['citation_revision']
            self.c.update_rating({'id':papers[0]['id'],'rating':-1})
            self.assertEqual(self.c.status()['citation_changes'],1) # no-op does not count
            self.c.interests('new interests')
            self.assertEqual(self.c.status()['citation_revision'],revision+1)
            self.c.store.save_profile(Profile(likes=papers[:28],dislikes=papers[28:31]))
            self.assertEqual(self.c.status()['citation_revision'],revision+2)
            self.assertEqual(self.c.status()['citation_changes'],0)

    def test_citation_readiness_transition_invalidates_before_five_changes(self):
        papers=[{**self.paper,'id':f'2401.{i:05d}'} for i in range(30)]
        self.c.store.save_profile(Profile(likes=papers[:26],dislikes=papers[26:29]))
        state=self.c.status()
        with patch('lens.feed.bridge.fetch_paper',return_value=papers[29]):
            updated=self.c.update_rating({'id':papers[29]['id'],'rating':1})
        self.assertEqual(updated['need_ratings'],0)
        self.assertEqual(updated['citation_revision'],state['citation_revision']+1)

    def test_citation_match_failure_keeps_paper_saveable(self):
        papers=[{**self.paper,'id':f'2401.{i:05d}'} for i in range(30)]
        self.c.store.save_profile(Profile(likes=papers[:27],dislikes=papers[27:]))
        ranker=Mock();ranker.ready.return_value=0;ranker.rank.side_effect=RuntimeError('test failure')
        self.c.rankers['tabpfn-fast']=ranker
        self.c.embedder=Mock();self.c.embedder.papers.side_effect=lambda rows:np.ones((len(rows),2))
        with patch.dict('os.environ',{'TABPFN_TOKEN':'test-credential'}):
            code,data=self.request('/api/paper-match?id=2207.01848')
        self.assertEqual(code,200);self.assertIsNone(data['match'])
        self.assertIn('still save',data['warning'])
        self.assertEqual(self.request('/api/rate',{'id':self.paper['id'],'rating':1})[0],200)

if __name__ == '__main__': unittest.main()
