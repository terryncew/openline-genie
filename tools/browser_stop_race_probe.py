"""Actual R7.2 product-page JS in Chromium with delayed, guarded HTTP mocks.
This is an isolated UI state-machine falsifier, NOT a full live-server browser acceptance.
Run: python browser_stop_race_probe.py <path-to-extracted-openline-genie>
"""
import json,sys
from pathlib import Path
from playwright.sync_api import sync_playwright
src=Path(sys.argv[1]).resolve()
html=(src/'openline_five_products.html').read_text()
script=r'''(scenario) => {
  window.raceProbe = {scenario,earlyClear:0,stopComplete:false,stopRequested:false,
    stopped:false,epoch:1,clearAccepted:0,clearRejected:0,stopAccepted:0};
  window.fetch = async (input,opts={}) => {
    const u=String(input).split('?')[0];
    const reply=(obj,status=200) => new Response(JSON.stringify(obj),{status,headers:{'Content-Type':'application/json'}});
    if(u==='/api/five_products/state') return reply({engine_status:{stopped:window.raceProbe.stopped,stop_epoch:window.raceProbe.epoch,paid_model_enabled:false},products:{}});
    if(u==='/api/stop') {
      window.raceProbe.stopRequested=true;
      await new Promise(r=>setTimeout(r,500));
      window.raceProbe.stopComplete=true;
      if(scenario==='stop_failure') return reply({error:'stop_receiver_unavailable'},503);
      window.raceProbe.stopped=true;window.raceProbe.epoch++;window.raceProbe.stopAccepted++;
      const ownEpoch=window.raceProbe.epoch;
      if(scenario==='intervening_stop') window.raceProbe.epoch++;
      return reply({status:'STOPPED',new_epoch:ownEpoch});
    }
    if(u==='/api/clear_stop') {
      if(!window.raceProbe.stopComplete) window.raceProbe.earlyClear++;
      const body=JSON.parse(opts.body||'{}');
      if(!window.raceProbe.stopped || (body.expected_epoch!==undefined && body.expected_epoch!==window.raceProbe.epoch)) {
        window.raceProbe.clearRejected++;
        return reply({error:window.raceProbe.stopped?'stale_owner_intent':'stop_not_active'},409);
      }
      window.raceProbe.stopped=false;window.raceProbe.epoch++;window.raceProbe.clearAccepted++;
      return reply({status:'ACTIVE',active_epoch:window.raceProbe.epoch});
    }
    return reply({error:'unknown'},404);
  };
}'''
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
    failed=[]
    for scenario in ('normal','intervening_stop','stop_failure'):
        page=browser.new_page(viewport={'width':390,'height':844})
        page.goto('about:blank')
        page.evaluate(script,scenario)
        page.set_content(html,wait_until='domcontentloaded',timeout=15000)
        page.wait_for_selector('#btn-trigger-stop:not(.hidden)',timeout=15000)
        page.click('#btn-trigger-stop')
        page.wait_for_selector('#btn-clear-stop:not(.hidden)',timeout=2000)
        page.click('#btn-clear-stop')
        page.wait_for_timeout(1200)
        data=page.evaluate('window.raceProbe')
        data['banner']=page.locator('#product-action-banner').inner_text()
        # normal -> STOP acknowledged before explicit Resume, ended active.
        # intervening -> receiver refuses old owner intent, newer STOP survives.
        # stop failure -> never issue a clear without a valid STOP receipt.
        expected={'normal':(False,1,0),'intervening_stop':(True,0,1),'stop_failure':(False,0,0)}[scenario]
        actual=(data['stopped'],data['clearAccepted'],data['clearRejected'])
        ok=actual==expected and data['earlyClear']==0 and data['stopComplete']
        if not ok:failed.append(scenario)
        print(json.dumps({'pass':ok,**data}))
        page.close()
    browser.close()
    if failed:sys.exit(f'FAILED: {failed}')
