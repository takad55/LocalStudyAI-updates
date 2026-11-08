"""Generated fixtures only. No user documents, cloud calls, or real-model assumptions."""
import copy
import http.client
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from zipfile import ZipFile
import pymupdf
from localstudy import workbench as w
from localstudy.config import WORKSPACE_ROOT
from localstudy.fileops.safety import Scope, SafetyError
from localstudy.fileops.engine import Engine

class FakeAI:
    def __init__(self, reply='原文の要点です。[S1]'):self.reply=reply;self.calls=0
    def generate(self,prompt,**kwargs):self.calls+=1;return self.reply

class Fixture(unittest.TestCase):
    def setUp(self):
        base=WORKSPACE_ROOT/'practice'/'_v1_tests';base.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=base);self.parent=Path(self.tmp.name)
        self.root=self.parent/'資料 日本語';self.root.mkdir();self.scope=Scope(self.root)
        self.db=self.parent/'index.sqlite3'
    def tearDown(self):self.tmp.cleanup()
    def file(self,name='講義.txt',text='流体力学 講義資料 ベルヌーイの式の前提は非粘性・定常流です。'):
        p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8');return p
    def archive(self,name,entries):
        p=self.root/name
        with ZipFile(p,'w') as z:
            for n,text in entries.items():z.writestr(n,text)
        return p
    def indexed(self):
        self.file();return w.build_index(self.scope,path=self.db)

class DocumentTests(Fixture):
    def test_text_locator_and_original_unchanged(self):
        p=self.file();before=p.read_bytes();doc=w.read_doc(self.scope,p.name)
        self.assertEqual(doc['sections'][0]['location'],'行1–1');self.assertEqual(p.read_bytes(),before)
        self.assertIn('ベルヌーイ',doc['sections'][0]['text'])
    def test_cp932(self):
        p=self.root/'notes.txt';p.write_bytes('熱工学の講義'.encode('cp932'))
        self.assertIn('熱工学',w.read_doc(self.scope,p.name)['sections'][0]['text'])
    def test_pdf_page_locators(self):
        p=self.root/'two.pdf'
        with pymupdf.open() as doc:
            doc.new_page().insert_text((50,50),'Heat transfer');doc.new_page().insert_text((50,50),'Second page');doc.save(p)
        result=w.read_doc(self.scope,p.name)
        self.assertEqual([s['location'] for s in result['sections']],['p.1','p.2'])
        self.assertTrue(result['warnings'])
    def test_docx_paragraph_locator(self):
        self.archive('test.docx',{'word/document.xml':'<document><p><r><t>熱工学</t></r></p><p><r><t>講義</t></r></p></document>'})
        result=w.read_doc(self.scope,'test.docx');self.assertIn('段落',result['sections'][0]['location']);self.assertIn('熱工学',result['sections'][0]['text'])
    def test_pptx_natural_slide_order(self):
        self.archive('test.pptx',{'ppt/slides/slide10.xml':'<slide><t>ten</t></slide>','ppt/slides/slide2.xml':'<slide><t>two</t></slide>'})
        result=w.read_doc(self.scope,'test.pptx');self.assertEqual([s['location'] for s in result['sections']],['スライド 2','スライド 10'])
    def test_xlsx_shared_inline_formula_and_sheet(self):
        self.archive('test.xlsx',{'xl/workbook.xml':'<workbook xmlns:r="r"><sheets><sheet name="測定" r:id="rId1"/></sheets></workbook>','xl/_rels/workbook.xml.rels':'<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>','xl/sharedStrings.xml':'<sst><si><t>温度</t></si></sst>','xl/worksheets/sheet1.xml':'<worksheet><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="inlineStr"><is><t>熱流量</t></is></c><c r="C1"><f>2+2</f><v>4</v></c></row></sheetData></worksheet>'})
        doc=w.read_doc(self.scope,'test.xlsx');s=doc['sections'][0]
        self.assertIn('測定',s['location']);self.assertIn('温度',s['text']);self.assertIn('熱流量',s['text']);self.assertIn('2+2',s['text'])
    def test_xml_dtd_rejected(self):
        self.archive('test.docx',{'word/document.xml':'<!DOCTYPE x [<!ENTITY e "secret">]><document><p><t>&e;</t></p></document>'})
        with self.assertRaises(ValueError):w.read_doc(self.scope,'test.docx')
    def test_secrets_excluded(self):
        for name in ('.env','credentials.json','id_rsa','server.key','config.json'):self.file(name,'sensitive')
        self.file('ordinary.txt','lecture')
        files,skipped,complete=w.walk(self.scope)
        self.assertEqual(files,['ordinary.txt']);self.assertTrue(complete);self.assertGreaterEqual(len(skipped),5)
    def test_path_escape_rejected(self):
        with self.assertRaises(SafetyError):w.read_doc(self.scope,'../outside.txt')
    def test_large_file_rejected_before_read(self):
        p=self.file();
        with patch.object(w,'MAX_BYTES',2):
            with self.assertRaises(ValueError):w.read_doc(self.scope,p.name)
    def test_app_subfolder_excluded(self):
        self.file('project/package.json','{}');self.file('project/data.txt','project data');self.file('normal/a.txt','ordinary')
        files,_,_=w.walk(self.scope);self.assertNotIn('project/data.txt',files);self.assertIn('normal/a.txt',files)
    def test_walk_partial_reports_limit(self):
        self.file('a.txt');self.file('b.txt');files,skipped,complete=w.walk(self.scope,limit=1)
        self.assertFalse(complete);self.assertTrue(skipped)

class LibraryTests(Fixture):
    def test_incremental_index(self):
        first=self.indexed();second=w.build_index(self.scope,path=self.db)
        self.assertEqual(first['updated'],1);self.assertEqual(second['reused'],1);self.assertEqual(w.index_stats(self.db)['documents'],1)
    def test_japanese_search_citation(self):
        self.indexed();r=w.search('ベルヌーイ',root=str(self.root),path=self.db)
        self.assertEqual(r['sources'][0]['citation'],'S1');self.assertEqual(r['sources'][0]['relative'],'講義.txt')
        self.assertIn('行',r['sources'][0]['location'])
    def test_changed_file_not_served(self):
        self.indexed();self.file(text='現在は熱工学の資料です。')
        r=w.search('ベルヌーイ',path=self.db);self.assertEqual(r['sources'],[]);self.assertTrue(r['warnings'])
    def test_same_size_timestamp_change_detected_by_hash(self):
        p=self.file('a.txt','ABCDE heat');w.build_index(self.scope,path=self.db);st=p.stat()
        p.write_text('XXXXX xxxx',encoding='utf-8');os.utime(p,ns=(st.st_atime_ns,st.st_mtime_ns))
        r=w.search('heat',path=self.db);self.assertEqual(r['sources'],[])
    def test_deleted_index_entry_removed(self):
        self.indexed();(self.root/'講義.txt').unlink();r=w.build_index(self.scope,path=self.db)
        self.assertEqual(r['removed'],1);self.assertEqual(w.index_stats(self.db)['documents'],0)
    def test_cancel_does_not_prune_index(self):
        self.indexed();r=w.build_index(self.scope,path=self.db,cancelled=lambda:True)
        self.assertFalse(r['complete']);self.assertEqual(w.index_stats(self.db)['documents'],1)
    def test_no_result_does_not_call_model(self):
        model=FakeAI();r=w.answer({'sources':[]},model);self.assertEqual(model.calls,0);self.assertFalse(r['grounded'])
    def test_unknown_citation_suppressed(self):
        self.indexed();r=w.search('ベルヌーイ',path=self.db)
        out=w.answer(r,FakeAI('unsupported [S99]'));self.assertFalse(out['grounded']);self.assertNotIn('unsupported',out['answer'])
    def test_valid_citation_returned(self):
        self.indexed();r=w.answer(w.search('ベルヌーイ',path=self.db),FakeAI());self.assertTrue(r['grounded']);self.assertIn('[S1]',r['answer'])
    def test_summary_coverage(self):
        self.indexed();model=FakeAI();r=w.summarize(self.scope,['講義.txt'],model,path=self.db)
        self.assertEqual(len(r['coverage']),1);self.assertGreater(r['coverage'][0]['characters_used'],0);self.assertIn('講義.txt',r['answer']);self.assertTrue(model.calls)
    def test_summary_unknown_document_rejected(self):
        with self.assertRaises(ValueError):w.summarize(self.scope,['missing.txt'],FakeAI(),path=self.db)
    def test_summary_changed_document_rejected(self):
        self.indexed();self.file(text='changed')
        with self.assertRaises(SafetyError):w.summarize(self.scope,['講義.txt'],FakeAI(),path=self.db)
    def test_queries_parameterized(self):
        self.indexed();w.search("' OR 1=1 -- DROP TABLE documents",path=self.db)
        self.assertEqual(w.index_stats(self.db)['documents'],1)
    def test_empty_query_rejected(self):
        with self.assertRaises(ValueError):w.search('',path=self.db)

class OrganizerTests(Fixture):
    def test_intents_and_unsupported(self):
        for text,expected in [('整理して','organize'),('大学資料を分けて','academic'),('不要候補を調べて','cleanup'),('重複を整理','duplicates'),('資料を検索','search')]:self.assertEqual(w.intent(text),expected)
        with self.assertRaises(ValueError):w.intent('完全削除して')
        with self.assertRaises(ValueError):w.intent('こんにちは')
    def test_analysis_does_not_modify_files(self):
        p=self.file('流体力学_第2回演習.txt');before=p.read_bytes();r=w.analyze(self.scope,mode='academic')
        self.assertTrue(r['candidates']);self.assertEqual(p.read_bytes(),before);self.assertFalse((self.root/'大学資料').exists())
        self.assertIn('第02回',r['candidates'][0]['destination'])
    def test_old_installer_unselected(self):
        p=self.file('oldsetup.exe','not an executable');old=time.time()-100*86400;os.utime(p,(old,old))
        r=w.analyze(self.scope,mode='cleanup');self.assertEqual(len(r['candidates']),1);self.assertFalse(r['candidates'][0]['selected']);self.assertIn('断定',r['candidates'][0]['reason'])
    def test_recent_installer_not_cleanup_candidate(self):
        self.file('newsetup.exe','not executable');r=w.analyze(self.scope,mode='cleanup');self.assertEqual(r['candidates'],[])
    def test_unrelated_doc_kept_in_academic_mode(self):
        self.file('memo.txt','Buy soap and milk');r=w.analyze(self.scope,mode='academic')
        self.assertEqual(r['candidates'][0]['action'],'keep');self.assertFalse(r['candidates'][0]['selected'])
    def test_model_cannot_invent_course(self):
        p=self.file('memo.txt','unrelated data');d=w.read_doc(self.scope,p.name)
        result=w.classify(d,FakeAI('{"course":"熱工学","kind":"講義資料","reason":"guess"}'))
        self.assertEqual(result[0],'不明')
    def test_ambiguous_electronics_stays_uncertain(self):
        p=self.file('arduino.txt','Arduino tinkercad');result=w.classify(w.read_doc(self.scope,p.name))
        self.assertEqual(result[0],'不明')
    def test_plan_changed_source_rejected(self):
        p=self.file();r=w.analyze(self.scope,mode='academic');p.write_text('changed',encoding='utf-8')
        with self.assertRaises(SafetyError):w.make_plan(self.scope,r,[r['candidates'][0]['id']])
    def test_plan_path_escape_rejected(self):
        self.file();r=w.analyze(self.scope,mode='academic');key=r['candidates'][0]['id']
        with self.assertRaises(SafetyError):w.make_plan(self.scope,r,[key],{key:'../outside.txt'})
    def test_plan_collision_keeps_both(self):
        self.file();r=w.analyze(self.scope,mode='academic');c=r['candidates'][0];self.file(c['destination'],'existing')
        p=w.make_plan(self.scope,r,[c['id']]);move=next(a for a in p.actions if a.kind=='move')
        self.assertIn('(整理2)',move.dst);self.assertTrue(self.scope.path(c['destination']).exists())
    def test_duplicate_survivor_guard(self):
        self.file('orig.txt','same');self.file('copy.txt','same');r=w.analyze(self.scope,mode='duplicates')
        self.assertEqual(len(r['candidates']),1);plan=w.make_plan(self.scope,r,[r['candidates'][0]['id']])
        self.assertEqual(len(plan.guards),1);self.assertNotEqual(plan.actions[0].src,plan.guards[0]['relative'])
    def test_move_execute_and_undo(self):
        self.file();r=w.analyze(self.scope,mode='academic');plan=w.make_plan(self.scope,r,[r['candidates'][0]['id']]);engine=Engine(self.parent/'history')
        result=engine.run(plan,plan.digest());self.assertFalse(result.error)
        journal=engine.journals()[0];undo,notes=engine.undo_plan(journal.stem);back=engine.run(undo,undo.digest(),undo_transaction=journal.stem)
        self.assertFalse(back.error);self.assertTrue((self.root/'講義.txt').exists())
    def test_public_report_omits_fingerprints(self):
        self.file();r=w.public_report(w.analyze(self.scope,mode='academic'))
        self.assertNotIn('guards',r);self.assertNotIn('before',r['candidates'][0])
    def test_nested_nonacademic_not_disrupted(self):
        self.file('folder/memo.txt','notes');r=w.analyze(self.scope,mode='organize')
        self.assertEqual(r['candidates'],[])

class AdviceTests(Fixture):
    def report(self):self.file();return w.analyze(self.scope,mode='academic')
    def payload(self,r,**override):
        c=r['candidates'][0];row={'id':c['id'],'decision':'move','destination':'授業/保管.txt','reason':'checked'};row.update(override)
        return json.dumps({'report_id':r['id'],'decisions':[row]})
    def test_consult_no_absolute_root(self):
        r=self.report();text=w.consult(self.scope,r,[r['candidates'][0]['id']]);self.assertNotIn(str(self.root),text);self.assertIn(r['id'],text)
    def test_consult_text_opt_in(self):
        r=self.report();c=r['candidates'][0]
        self.assertNotIn('非粘性',w.consult(self.scope,r,[c['id']]))
        self.assertIn('非粘性',w.consult(self.scope,r,[c['id']],True))
    def test_redact_common_secrets(self):
        text='mail=student@example.test password=not-real '+('ghp_'+'x'*30)
        safe=w.redact(text);self.assertNotIn('student@',safe);self.assertNotIn('not-real',safe);self.assertNotIn('ghp_',safe)
    def test_import_advice_is_unselected_and_not_executed(self):
        r=self.report();out=w.import_advice(self.scope,r,self.payload(r));self.assertFalse(out['candidates'][0]['selected']);self.assertFalse((self.root/'授業').exists())
    def test_foreign_report_rejected(self):
        r=self.report();obj=json.loads(self.payload(r));obj['report_id']='foreign'
        with self.assertRaises(SafetyError):w.import_advice(self.scope,r,json.dumps(obj))
    def test_unknown_id_rejected(self):
        r=self.report()
        with self.assertRaises(SafetyError):w.import_advice(self.scope,r,self.payload(r,id='unknown'))
    def test_outside_move_rejected(self):
        r=self.report()
        with self.assertRaises(SafetyError):w.import_advice(self.scope,r,self.payload(r,destination='C:\\Windows\\bad.txt'))
    def test_command_rejected(self):
        r=self.report()
        with self.assertRaises(SafetyError):w.import_advice(self.scope,r,self.payload(r,decision='execute'))

class JobTests(unittest.TestCase):
    def test_progress_completion(self):
        jobs=w.Jobs()
        def work(progress,cancel):progress(1,1,'done');return {'value':1}
        jobs.start('test',work)
        for _ in range(100):
            if not jobs.active():break
            time.sleep(.01)
        self.assertEqual(jobs.snapshot()['status'],'done');self.assertEqual(jobs.snapshot()['result']['value'],1)
    def test_cancel_and_single_job(self):
        jobs=w.Jobs()
        def work(progress,cancel):
            while not cancel():time.sleep(.005)
            return {'partial':True}
        jobs.start('test',work)
        with self.assertRaises(ValueError):jobs.start('second',work)
        jobs.cancel.set()
        for _ in range(100):
            if not jobs.active():break
            time.sleep(.01)
        self.assertEqual(jobs.snapshot()['status'],'cancelled')

class HTTPTests(Fixture):
    def setUp(self):
        super().setUp()
        from localstudy import webapp
        self.module=webapp;self.state=webapp.State();self.state.set_scope(self.root)
        with patch.object(webapp,'PORT',0):self.server=webapp.LocalServer(self.state)
        self.port=self.server.server_address[1];self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join(3);super().tearDown()
    def request(self,method,path,body=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=4)
        conn.request(method,path,body=body,headers=headers or {});res=conn.getresponse();data=res.read();status=res.status;conn.close();return status,data
    def post(self,obj,**headers):
        h={'Content-Type':'application/json','Origin':f'http://127.0.0.1:{self.port}','X-LocalStudy-Token':self.state.token};h.update(headers)
        status,data=self.request('POST','/api/action',json.dumps(obj).encode(),h);return status,json.loads(data)
    def test_assets_and_boot(self):
        for path in ['/','/assets/workbench.js','/assets/workbench.css','/api/boot']:
            status,data=self.request('GET',path);self.assertEqual(status,200,path);self.assertTrue(data)
    def test_foreign_origin_rejected(self):
        status,_=self.post({'action':'wb_stats'},Origin='https://evil.example');self.assertEqual(status,403)
    def test_invalid_token_rejected(self):
        status,_=self.post({'action':'wb_stats'},**{'X-LocalStudy-Token':'bad'});self.assertEqual(status,403)
    def test_foreign_host_rejected(self):
        status,_=self.request('GET','/api/boot',headers={'Host':'evil.example'});self.assertEqual(status,403)
    def test_background_analysis_pollable(self):
        self.file();status,data=self.post({'action':'wb_start','task':'analyze','mode':'academic','use_ai':False});self.assertEqual(status,200)
        for _ in range(100):
            status,data=self.post({'action':'wb_job'});self.assertEqual(status,200)
            if data['result']['job']['status']!='running':break
            time.sleep(.01)
        self.assertEqual(data['result']['job']['status'],'done');self.assertTrue(data['state']['workbench']['report']['candidates'])
    def test_scope_switch_blocked_while_working(self):
        self.state.workbench.jobs.start('block',lambda p,c: self.wait_cancel(c))
        status,_=self.post({'action':'root','path':str(self.root)});self.assertEqual(status,400)
        self.state.workbench.jobs.cancel.set()
    @staticmethod
    def wait_cancel(cancel):
        while not cancel():time.sleep(.005)
        return {}

if __name__=='__main__':unittest.main()
