# Optional development test. Requires playwright and a Chromium browser.
from pathlib import Path
import re, base64, json, sys, tempfile, os
from playwright.sync_api import sync_playwright
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app.config import ROOT,Settings
from backend.app.main import create_app
out=ROOT/'docs/screenshots';out.mkdir(exist_ok=True)
cache={}
def module_url(path):
 path=path.resolve()
 if path in cache:return cache[path]
 source=path.read_text()
 def replace(match):
  return 'from '+json.dumps(module_url(path.parent/match.group(1)))
 source=re.sub(r'''from\s+['"](\.[^'"]+)['"]''',replace,source)
 url='data:text/javascript;base64,'+base64.b64encode(source.encode()).decode()
 cache[path]=url
 return url
entry=module_url(ROOT/'frontend/src/app.js')
with tempfile.TemporaryDirectory() as temp:
 settings=Settings(_env_file=None,app_env='test',auth_mode='demo',solver_engine='demo_search',database_path=temp+'/ui.sqlite3',dataset_path=str(ROOT/'data'/'demo_data.json'))
 with TestClient(create_app(settings)) as client, sync_playwright() as p:
  options = {'headless': True}
  if os.getenv('CHROMIUM_EXECUTABLE'): options['executable_path'] = os.environ['CHROMIUM_EXECUTABLE']
  browser=p.chromium.launch(**options)
  errors=[]
  def bootstrap(width=1512,height=1100):
   page=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1)
   page.on('pageerror',lambda error:errors.append(str(error)))
   def call_api(payload):
    response=client.request(payload['method'],payload['path'],headers=payload['headers'],content=payload.get('body'))
    return {'status':response.status_code,'body':response.text}
   page.expose_function('__testApi',call_api)
   page.set_content('<!doctype html><html><head><title>RailPlan</title></head><body><div id="app">Loading...</div></body></html>')
   page.add_style_tag(content=(ROOT/'frontend/styles.css').read_text())
   page.evaluate('''() => {
      const values={};
      Object.defineProperty(window,'sessionStorage',{value:{getItem:k=>values[k]||null,setItem:(k,v)=>{values[k]=v;},removeItem:k=>{delete values[k];}}});
      window.fetch=async (path, options={})=>{
        const r=await window.__testApi({path,method:options.method||'GET',headers:options.headers||{},body:options.body});
        return new Response(r.body,{status:r.status,headers:{'content-type':'application/json'}});
      };
   }''')
   page.add_script_tag(type='module',content=f'import {json.dumps(entry)};')
   page.wait_for_selector('[data-demo="demo-officer"]')
   page.on('dialog',lambda d:d.accept())
   return page
  page=bootstrap()
  page.screenshot(path=str(out/'01-login.png'),full_page=True)
  page.locator('[data-demo="demo-officer"]').click();page.wait_for_selector('.workspace-grid')
  page.screenshot(path=str(out/'02-officer.png'),full_page=True)
  page.locator('[data-action="generate"]').first.click();page.wait_for_selector('[data-action="commit"]')
  page.screenshot(path=str(out/'03-proposal.png'),full_page=True)
  page.locator('[data-action="commit"]').click();page.wait_for_function("document.body.textContent.includes('Plan published.')")
  page.locator('[data-action="logout"]').click();page.wait_for_selector('[data-demo="demo-track"]')
  page.locator('[data-demo="demo-track"]').click();page.wait_for_selector('[data-nav="new-request"]')
  page.screenshot(path=str(out/'04-requester.png'),full_page=True)
  page.locator('[data-nav="new-request"]').first.click();page.wait_for_selector('#request-form')
  page.locator('[name="title"]').fill('Browser smoke test request')
  page.locator('[name="work_sector"]').select_option('S06')
  page.locator('[name="required_skill"]').select_option('inspection')
  page.locator('[name="allow_next_night"]').check()
  page.screenshot(path=str(out/'05-request-form.png'),full_page=True)
  page.locator('#request-form button[type="submit"]').click()
  page.wait_for_function("document.body.textContent.includes('Browser smoke test request')")
  # Another browser session reads persisted backend state.
  second=bootstrap()
  second.locator('[data-demo="demo-track"]').click()
  second.wait_for_function("document.body.textContent.includes('Browser smoke test request')")
  assert second.locator('[data-action="generate"]').count()==0
  second.locator('[data-cancel]').first.click();second.wait_for_function("document.body.textContent.includes('Request withdrawn.')")
  second.set_viewport_size({'width':390,'height':844})
  second.screenshot(path=str(out/'06-mobile.png'),full_page=True)
  assert not errors,errors
  print(json.dumps({'browser_smoke':'passed','page_errors':errors,'api_transport':'FastAPI TestClient bridge (no network)','screenshots':len(list(out.glob('*.png')))},indent=2))
  browser.close()
