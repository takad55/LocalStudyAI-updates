"""Headless UI integration test with generated practice data, no real user files."""
import json
from pathlib import Path
import sys
import threading
import time
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent.parent
APP=ROOT/'build'/'app'
sys.path.insert(0,str(APP))
from localstudy import webapp
from playwright.sync_api import sync_playwright

def main():
    state=webapp.State()
    with patch.object(webapp,'PORT',0):server=webapp.LocalServer(state)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    errors=[]
    url='http://127.0.0.1:'+str(server.server_address[1])
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            page=browser.new_page(viewport={'width':1365,'height':1000},device_scale_factor=1)
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(url,wait_until='networkidle')
            page.wait_for_function('window.app !== null || typeof app !== "undefined" && app !== null')
            page.locator('#wbPractice').click()
            page.wait_for_function('app.root.includes("統合練習")')
            page.locator('#wbAI').uncheck()
            page.locator('#wbRun').click()
            page.wait_for_function('app.workbench && app.workbench.report && app.workbench.report.candidates.length >= 3',timeout=15000)
            page.wait_for_timeout(1800)
            assert page.locator('.wb-candidate').count()>=3
            # No filesystem changes until explicit plan approval.
            assert not (state.scope.root/'大学資料').exists()
            page.screenshot(path=str(ROOT/'build'/'workbench-preview.png'),full_page=True)
            page.set_viewport_size({'width':1024,'height':850})
            page.screenshot(path=str(ROOT/'build'/'compact-preview.png'),full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth+2'), 'horizontal overflow'
            # Exercise destination editing and plan generation; never approve execution.
            page.locator('#wbPlan').click()
            page.wait_for_function('app.actions.length > 0')
            assert all(a.kind in ('move','mkdir') for a in state.plan.actions)
            assert not (state.scope.root/'大学資料').exists()
            page.on('dialog',lambda d:d.accept())
            page.locator('#clearPlan').click()
            page.wait_for_function('app.actions.length === 0')
            page.locator('button.nav-link[data-view="library"]').click()
            page.locator('#wbIndex').click()
            page.wait_for_function('document.querySelector("#wbDocuments").textContent.includes("熱工学")',timeout=20000)
            page.locator('#wbQuery').fill('ベルヌーイ')
            page.locator('#wbSearch').click()
            page.wait_for_function('document.querySelector("#wbSources").textContent.includes("流体力学")',timeout=15000)
            page.locator('.wb-source').first.locator('summary').click()
            page.set_viewport_size({'width':1365,'height':1000})
            page.screenshot(path=str(ROOT/'build'/'library-preview.png'),full_page=True)
            assert not errors,errors
            report={'browser':'Chromium','server':'real HTTP local server','checks':['boot','practice','read-only classification','candidate list','compact layout','move plan creation','no execution without approval','index creation','Japanese text search','source location display'],'javascript_errors':errors,'real_ollama':'not tested; read-only rules and search exercised'}
            (ROOT/'build'/'browser_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(report,ensure_ascii=False))
            browser.close()
    finally:
        server.shutdown();server.server_close();thread.join(5)

if __name__=='__main__':main()
