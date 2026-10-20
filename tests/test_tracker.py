import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tracker import transition, persist_run, evidence, wd_observe, web_observe, canonical, focuslight_detail
from render import build

AT='2026-10-20T05:00:00+08:00'
LATER='2026-10-21T05:00:00+08:00'
def obs(state='open',key='demo:1',at=AT):
    return {'id':key,'source':'test','title':'薄膜工艺实习生','company':'测试企业（仅测试夹具）','location':'北京','url':'https://example.com/job/1','description':'硕士 材料 science','conditions':'材料硕士','evidence':evidence(state,'https://example.com/job/1','test fixture','test',at)}

class Transitions(unittest.TestCase):
    def test_new_then_still_open(self):
        r=transition({'jobs':{}},[obs()],AT)
        self.assertEqual(r['jobs']['demo:1']['status'],'new')
        r=transition(r,[obs(at=LATER)],LATER)
        self.assertEqual(r['jobs']['demo:1']['status'],'open')
        self.assertEqual(r['jobs']['demo:1']['recommended_at'],AT)

    def test_only_previously_recommended_can_close(self):
        r=transition({'jobs':{}},[obs('closed')],AT)
        self.assertFalse(r['jobs'])
        pending=transition({'jobs':{}},[obs('unverified')],AT)
        pending=transition(pending,[obs('closed',at=LATER)],LATER)
        self.assertNotEqual(pending['jobs']['demo:1']['status'],'closed')
        r=transition({'jobs':{}},[obs()],AT)
        r=transition(r,[obs('closed',at=LATER)],LATER)
        j=r['jobs']['demo:1']
        self.assertEqual(j['status'],'closed')
        self.assertEqual(j['closure_evidence']['state'],'closed')
        self.assertEqual(j['recommended_at'],AT)

    def test_network_failure_and_disappearance_never_close(self):
        r=transition({'jobs':{}},[obs()],AT)
        for inputs in [[obs('unverified',at=LATER)],[]]:
            with self.subTest(inputs=inputs):
                updated=transition(r,inputs,LATER)
                self.assertEqual(updated['jobs']['demo:1']['status'],'unverified')
                self.assertEqual(updated['jobs']['demo:1']['recommended_at'],AT)
        self.assertEqual(r['jobs']['demo:1']['status'],'new')

    def test_uncertainty_does_not_erase_confirmed_closure(self):
        r=transition({'jobs':{}},[obs()],AT)
        r=transition(r,[obs('closed',at=LATER)],LATER)
        r=transition(r,[obs('unverified',at=LATER)],LATER)
        self.assertEqual(r['jobs']['demo:1']['status'],'closed')
        self.assertIn('closure_evidence',r['jobs']['demo:1'])

    def test_open_after_pending_is_new_on_confirmation_day(self):
        r=transition({'jobs':{}},[obs('unverified')],AT)
        r=transition(r,[obs(at=LATER)],LATER)
        self.assertEqual(r['jobs']['demo:1']['status'],'new')
        self.assertEqual(r['jobs']['demo:1']['recommended_at'],LATER)

class Preservation(unittest.TestCase):
    def test_multiple_days_and_same_day_reruns_survive(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); r=transition({'jobs':{}},[obs()],AT)
            persist_run(root,r,[],AT,'run-1')
            original=(root/'data/runs/run-1.json').read_bytes()
            persist_run(root,r,[],AT,'run-2')
            r=transition(r,[obs(at=LATER)],LATER)
            persist_run(root,r,[],LATER,'run-3')
            self.assertEqual((root/'data/runs/run-1.json').read_bytes(),original)
            self.assertEqual(json.loads((root/'data/history/2026-10-20.json').read_text())['runs'],['run-1','run-2'])
            self.assertTrue((root/'data/history/2026-10-21.json').exists())
            with self.assertRaises(FileExistsError):persist_run(root,r,[],AT,'run-1')
            build(root)
            page=(root/'docs/index.html').read_text(encoding='utf-8')
            self.assertLess(page.index('class="history-date">2026-10-21'),page.index('class="history-date">2026-10-20'))
            self.assertIn('run-1.json',page); self.assertIn('run-2.json',page)
            self.assertTrue((root/'docs/data/runs/run-1.json').exists())

    def test_untrusted_titles_are_escaped(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); j=obs();j['title']='<img src=x onerror=alert(1)>'
            r=transition({'jobs':{}},[j],AT)
            persist_run(root,r,[],AT,'safe')
            build(root); page=(root/'docs/index.html').read_text(encoding='utf-8')
            self.assertNotIn('<img src=x',page)
            self.assertIn('&lt;img',page)

class OfficialEvidence(unittest.TestCase):
    def test_official_list_detail_requires_matching_title_and_application(self):
        job=obs();job['title']='薄膜工艺实习生'
        page='<h1>薄膜工艺实习生</h1><div class="fyxwbt">申请职位<a href="mailto:HR@focuslight.com">申请</a></div><div class="fyxwxqbjq">任职要求：材料硕士</div>'
        self.assertEqual(focuslight_detail(job,page,AT)['evidence']['state'],'open')
        self.assertEqual(focuslight_detail(job,page.replace('mailto:','https:'),AT)['evidence']['state'],'unverified')
        job['title']='另一个职位'
        self.assertEqual(focuslight_detail(job,page,AT)['evidence']['state'],'unverified')

    def test_url_identity_keeps_job_query_parameters(self):
        self.assertEqual(canonical('https://example.com/job?post_id=123&utm_source=search'), 'https://example.com/job?post_id=123')

    def test_workday_requires_live_matching_id(self):
        source={'id':'test','company':'Test','host':'example.com','tenant':'t','board':'b'}
        post={'title':'Process Intern','externalPath':'/job/1','bulletFields':['REQ1'],'locationsText':'China'}
        class Response:
            status_code=200
            def json(self):return {'jobPostingInfo':{'jobReqId':'REQ1','jobDescription':'<p>Materials masters intern</p>','externalUrl':'https://example.com/apply','canApply':True,'posted':True}}
        with patch('tracker.session') as s:
            s.return_value.get.return_value=Response()
            self.assertEqual(wd_observe(source,post,AT)['evidence']['state'],'open')
            post['bulletFields']=['WRONG']
            self.assertEqual(wd_observe(source,post,AT)['evidence']['state'],'unverified')

    def test_http_404_is_uncertainty(self):
        class Response:status_code=404
        with patch('tracker.session') as s:
            s.return_value.get.return_value=Response()
            r=web_observe(obs(),{'official_domains':['example.com']},AT)
            self.assertEqual(r['evidence']['state'],'unverified')

if __name__=='__main__':unittest.main()
