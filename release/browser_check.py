"""Headless UI test with generated practice files; no CSP relaxation."""
import json
from pathlib import Path
import sys
import threading
import time
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent.parent
APP=ROOT/'build'/'app';sys.path.insert(0,str(APP))
from localstudy import webapp
from playwright.sync_api import sync_playwright, expect

def main():
    state=webapp.State()
    with patch.object(webapp,'PORT',0):server=webapp.LocalServer(state)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    errors=[];url='http://127.0.0.1:'+str(server.server_address[1])
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            page=browser.new_page(viewport={'width':1365,'height':1000},device_scale_factor=1)
            page.on('pageerror',lambda e:errors.append(str(e)))
            try:
                page.goto(url,wait_until='networkidle')
                expect(page.locator('#wbPractice')).to_be_visible()
                page.locator('#wbPractice').click()
                expect(page.locator('#wbRoot')).to_contain_text('統合練習',timeout=15000)
                page.locator('#wbAI').uncheck();page.locator('#wbRun').click()
                expect(page.locator('#wbSummary')).to_contain_text('移動候補',timeout=15000)
                expect(page.locator('.wb-candidate').first).to_be_visible()
                assert page.locator('.wb-candidate').count()>=3
                assert not (state.scope.root/'大学資料').exists()
                page.screenshot(path=str(ROOT/'build'/'workbench-preview.png'),full_page=True)
                page.set_viewport_size({'width':1024,'height':850})
                page.screenshot(path=str(ROOT/'build'/'compact-preview.png'),full_page=True)
                assert page.evaluate('() => document.documentElement.scrollWidth <= window.innerWidth+2'), 'horizontal overflow'
                page.locator('#wbPlan').click()
                expect(page.locator('#planList')).to_contain_text('大学資料',timeout=10000)
                assert state.plan.actions and all(a.kind in ('move','mkdir') for a in state.plan.actions)
                assert not (state.scope.root/'大学資料').exists()
                page.on('dialog',lambda d:d.accept());page.locator('#clearPlan').click()
                expect(page.locator('#planCount')).to_have_text('0')
                page.locator('button.nav-link[data-view="library"]').click();page.locator('#wbIndex').click()
                expect(page.locator('#wbDocuments')).to_contain_text('熱工学',timeout=20000)
                page.locator('#wbQuery').fill('ベルヌーイ');page.locator('#wbSearch').click()
                expect(page.locator('#wbSources')).to_contain_text('流体力学',timeout=15000)
                page.locator('.wb-source').first.locator('summary').click()
                page.set_viewport_size({'width':1365,'height':1000})
                page.screenshot(path=str(ROOT/'build'/'library-preview.png'),full_page=True)
                assert not errors,errors
                report={'browser':'Chromium','server':'real local HTTP server','checks':['boot','practice','read-only classification','candidate list','1024px compact layout','move plan creation','no execution without approval','index creation','Japanese text search','source location display'],'javascript_errors':errors,'real_ollama':'not tested; local rules and text search exercised'}
                (ROOT/'build'/'browser_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
                print(json.dumps(report,ensure_ascii=False))
            except Exception:
                page.screenshot(path=str(ROOT/'build'/'failure-preview.png'),full_page=True)
                print('JS errors:',errors)
                print('Visible page:',page.locator('body').inner_text()[-6000:])
                raise
            finally:browser.close()
    finally:server.shutdown();server.server_close();thread.join(5)

if __name__=='__main__':main()
