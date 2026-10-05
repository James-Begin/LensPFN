import json
import hashlib
import io
from urllib.error import HTTPError
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from lens.feed.references import resolve, _get, _datacite


class ReferenceResolutionTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.cache=Path(self.temp.name)
        self.details={'doi':'10.18653/v1/N19-1423','title':'BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding','authors':'Devlin et al.','year':'2019','reference':'Devlin et al., BERT.'}
        self.record={'title':self.details['title'],'authors':[{'name':'Jacob Devlin'}],'year':2019,'externalIds':{'ArXiv':'1810.04805'}}
        self.fallback=patch('lens.feed.references._datacite',return_value=[])
        self.fallback.start();self.addCleanup(self.fallback.stop)
    def tearDown(self):self.temp.cleanup()
    def test_doi_mapping_resolves_and_is_cached(self):
        with patch('lens.feed.references._get',return_value=self.record) as get:
            result=resolve(self.details,self.cache)
            again=resolve(self.details,self.cache)
        self.assertEqual(result['state'],'resolved')
        self.assertEqual(result['candidates'][0]['id'],'1810.04805')
        self.assertEqual(result,again);self.assertEqual(get.call_count,1)
    def test_title_search_resolves_automatically_and_filters_different_titles(self):
        details={**self.details,'doi':''}
        wrong={**self.record,'title':'An unrelated paper on image classification','externalIds':{'ArXiv':'2207.01848'}}
        with patch('lens.feed.references._get',return_value={'data':[wrong,self.record]}):result=resolve(details,self.cache)
        self.assertEqual(result['state'],'resolved')
        self.assertEqual([p['id'] for p in result['candidates']],['1810.04805'])
    def test_paper_without_arxiv_identity_does_not_get_an_invented_id(self):
        with patch('lens.feed.references._get',side_effect=[{**self.record,'externalIds':{'DOI':self.details['doi']}},{'data':[{**self.record,'externalIds':{}}]}]):result=resolve(self.details,self.cache)
        self.assertEqual(result['state'],'unresolved');self.assertEqual(result['candidates'],[])
    def test_exact_local_title_resolves_without_remote_requests(self):
        local={'id':'1810.04805','title':self.details['title'],'authors':['Jacob Devlin']}
        with patch('lens.feed.references._get') as get:result=resolve(self.details,self.cache,[local])
        self.assertEqual(result['state'],'resolved');get.assert_not_called()

    def test_search_orders_by_title_then_author_and_year(self):
        details={**self.details,'doi':''}
        similar={**self.record,'title':self.record['title']+': A Survey','externalIds':{'ArXiv':'2207.01848'}}
        wrong_author={**self.record,'authors':[{'name':'Other Author'}],'externalIds':{'ArXiv':'1706.03762'}}
        wrong_year={**self.record,'year':2020,'externalIds':{'ArXiv':'2301.00001'}}
        with patch('lens.feed.references._get',return_value={'data':[similar,wrong_author,wrong_year,self.record]}):
            result=resolve(details,self.cache)
        self.assertEqual(result['state'],'resolved')
        self.assertEqual([p['id'] for p in result['candidates']],['1810.04805','2301.00001','1706.03762','2207.01848'])

    def test_local_duplicate_titles_choose_matching_authors(self):
        local=[{'id':'2207.01848','title':self.details['title'],'authors':['Other Author']},
               {'id':'1810.04805','title':self.details['title'],'authors':['Jacob Devlin']}]
        with patch('lens.feed.references._get') as get:
            result=resolve(self.details,self.cache,local)
        self.assertEqual(result['candidates'][0]['id'],'1810.04805');get.assert_not_called()

    def test_old_confirmation_cache_does_not_prevent_automatic_resolution(self):
        key=hashlib.sha256(json.dumps(self.details,sort_keys=True).encode()).hexdigest()
        (self.cache/(key+'.json')).write_text(json.dumps({'state':'candidate','candidates':[]}))
        with patch('lens.feed.references._get',return_value=self.record) as get:
            result=resolve(self.details,self.cache)
        self.assertEqual(result['state'],'resolved');get.assert_called_once()

    def test_busy_search_does_not_block_identifier_lookup(self):
        busy=HTTPError('https://api.semanticscholar.org/graph/v1/paper/search',429,'busy',{},None)
        with patch('lens.feed.references._retry_after',{}),patch('lens.feed.references.time.sleep'),patch('lens.feed.references.urlopen',side_effect=[busy,io.BytesIO(b'{"title":"DOI record"}')]) as open:
            with self.assertRaises(RuntimeError):_get('search?query=BERT')
            self.assertEqual(_get('DOI:10.1234/example?fields=title')['title'],'DOI record')
            with self.assertRaises(RuntimeError):_get('search?query=other')
            self.assertEqual(open.call_count,2)

    def test_busy_semantic_search_falls_back_to_arxiv_doi_deposits(self):
        paper={'id':'1810.04805','title':self.details['title'],'authors':['Jacob Devlin'],'year':2019,'doi_match':False,'abstract':'Full paper abstract.','source':'datacite'}
        with patch('lens.feed.references._get',side_effect=RuntimeError('Rate limited')),patch('lens.feed.references._datacite',return_value=[paper]):
            result=resolve(self.details,self.cache)
            with patch('lens.feed.references._get') as get:
                again=resolve(self.details,self.cache)
        self.assertEqual(result['state'],'resolved');self.assertEqual(result['candidates'][0]['id'],'1810.04805')
        self.assertEqual(result,again);get.assert_not_called()

    def test_failed_doi_lookup_still_tries_title_lookup(self):
        with patch('lens.feed.references._get',side_effect=[RuntimeError('DOI unavailable'),{'data':[self.record]}]):
            result=resolve(self.details,self.cache)
        self.assertEqual(result['state'],'resolved')

    def test_all_providers_unavailable_is_retryable_and_not_cached(self):
        with patch('lens.feed.references._get',side_effect=TimeoutError()),patch('lens.feed.references._datacite',side_effect=TimeoutError()):
            result=resolve(self.details,self.cache)
        self.assertEqual(result['state'],'unavailable');self.assertEqual(list(self.cache.iterdir()),[])

    def test_unstructured_reference_selects_contained_title_and_filters_unrelated_papers(self):
        details={**self.details,'doi':'','title':'','reference':'Devlin et al. 2019. '+self.details['title']+'. Proceedings of NAACL.'}
        paper={'id':'1810.04805','title':self.details['title'],'authors':['Jacob Devlin'],'doi_match':False}
        unrelated={**paper,'id':'2207.01848','title':'A new computer vision algorithm'}
        with patch('lens.feed.references._get',side_effect=RuntimeError()),patch('lens.feed.references._datacite',return_value=[unrelated,paper]):
            result=resolve(details,self.cache)
        self.assertEqual([p['id'] for p in result['candidates']],['1810.04805'])

    def test_datacite_parser_keeps_only_real_arxiv_dois_with_scoring_metadata(self):
        self.fallback.stop()
        attributes={'titles':[{'title':self.details['title']}],'creators':[{'givenName':'Jacob','familyName':'Devlin'}],
                    'publicationYear':2018,'descriptions':[{'descriptionType':'Abstract','description':'An abstract.'}],
                    'subjects':[{'subject':'Computation and Language (cs.CL)'}],
                    'dates':[{'dateType':'Submitted','date':'2018-10-11T00:00:00Z'}]}
        rows=[{'id':'10.48550/arxiv.1810.04805','attributes':attributes},
              {'id':'10.48550/arxiv.invalid','attributes':attributes},
              {'id':'10.1234/a-different-repository','attributes':attributes}]
        with patch('lens.feed.references.time.sleep'),patch('lens.feed.references.urlopen',return_value=io.BytesIO(json.dumps({'data':rows}).encode())) as open:
            result=_datacite({**self.details,'doi':''})
        self.assertEqual(len(result),1);paper=result[0]
        self.assertEqual(paper['id'],'1810.04805');self.assertEqual(paper['authors'],['Jacob Devlin'])
        self.assertEqual(paper['created'],'2018-10-11');self.assertEqual(paper['abstract'],'An abstract.')
        self.assertEqual(paper['categories'],['cs.CL'])
        self.assertIn('sort=relevance',open.call_args.args[0].full_url)
