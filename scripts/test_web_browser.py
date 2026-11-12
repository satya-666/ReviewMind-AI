"""Real inference and feedback UX checks against a running isolated local API."""
import asyncio,json,os,sys
from pathlib import Path
from playwright.async_api import async_playwright,expect

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
REVIEW='The phone has excellent battery life and a great display, but the camera quality is disappointing.'

async def run():
    base=os.getenv('WEB_TEST_URL','http://127.0.0.1:8765')
    checks=[];errors=[];dialogs=[]
    database_url=os.getenv('WEB_TEST_DATABASE_URL','sqlite:///'+str(ROOT/'.cache/web/e2e-feedback.db'))
    from backend.app.db import Database,Feedback
    from sqlalchemy.orm import Session
    from sqlalchemy import text
    db=Database(database_url)
    def stored(identifier):
        with Session(db.engine) as session:
            row=session.get(Feedback,identifier)
            return {'request_id':row.request_id,'rating':row.rating,'message':row.message} if row else None
    async with async_playwright() as playwright:
        browser=await playwright.chromium.launch(headless=True)
        context=await browser.new_context(viewport={'width':1440,'height':1000})
        page=await context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('dialog',lambda dialog:dialogs.append(dialog.message))
        await page.goto(base,wait_until='networkidle')
        await expect(page.locator('h1')).to_have_text('Let’s understand your product reviews')
        await expect(page.locator('#welcome')).to_contain_text('No messages yet')
        assert await page.locator('.msg').count()==0
        assert await page.locator('[data-plan],#pbtn,#budget,#examples').count()==0
        await page.locator('#historyBtn').click();await expect(page.locator('#hist')).to_contain_text('No local chats yet')
        await page.keyboard.press('Escape');await expect(page.locator('#side')).to_be_hidden()
        checks.append('clean_empty_state_and_no_fake_account_plans_or_examples')
        await page.locator('#send').click();await expect(page.locator('#hint')).to_contain_text('Enter a message')
        async def cold_start(route):await asyncio.sleep(.7);await route.continue_()
        await page.route('**/api/chat/status',cold_start)
        await page.locator('#q').fill('Hello')
        async with page.expect_response('**/api/chat') as pending:
            await page.locator('#q').press('Enter')
            await expect(page.locator('#loading')).to_contain_text('wake up')
            await expect(page.locator('#send')).to_be_disabled()
        greeting=await (await pending.value).json();assert greeting['type']=='chat' and greeting['response_source']=='built_in'
        await page.unroute('**/api/chat/status',cold_start)
        checks.append('bounded_cold_start_get_before_single_post')
        await expect(page.locator('.response-source')).to_contain_text('not a language-model answer')
        await page.locator('#q').fill('Who are you?')
        async with page.expect_response('**/api/chat') as pending:await page.locator('#send').click()
        assert (await (await pending.value).json())['intent']=='conversation'
        await page.locator('#q').fill('Suggest a smartphone under ₹20,000')
        async with page.expect_response('**/api/chat') as pending:await page.locator('#send').click()
        recommendation=await (await pending.value).json();assert recommendation['provider_status']=='consent_required'
        await expect(page.locator('.chat-answer').last).to_contain_text('Gemini conversation is turned off')
        await page.locator('#startNew').click();await expect(page.locator('#welcome')).to_be_visible()
        await page.locator('#allowGemini').check();await page.locator('#q').fill('Hello')
        async with page.expect_response('**/api/chat') as pending:await page.locator('#send').click()
        missing=await (await pending.value).json();assert missing['error']['code']=='not_configured'
        sent=(await pending.value).request.post_data_json
        assert sent['history']==[] and sent['analysis_request_id'] is None
        await expect(page.locator('.error-card')).to_contain_text('Gemini is not configured')
        await expect(page.locator('.retry')).to_be_visible()
        await expect(page.locator('#q')).to_have_value('Hello')
        await page.locator('#allowGemini').uncheck();await page.locator('#startNew').click()
        checks.extend(['empty_message_validation','greeting_identity_and_recommendation_intents','provider_not_configured_is_explicit','new_chat_resets_conversation'])
        for message in ['Can you help me choose a phone?','My budget is ₹20,000.','I prefer Samsung.','Battery life matters most.','yes','okay','continue','tell me more','what next?']:
            await page.locator('#q').fill(message)
            async with page.expect_response('**/api/chat') as pending:await page.locator('#send').click()
            await expect(page.locator('#send')).to_be_enabled()
        sent=(await pending.value).request.post_data_json
        assert len(sent['history'])<=8 and sum(len(m['text']) for m in sent['history'])<=4000
        assert all(s in sent['history'][0]['text'] for s in ['₹20,000','Samsung','Battery life'])
        checks.append('user_preferences_survive_recent_context_window_without_canned_history')
        await page.locator('#startNew').click()
        await page.locator('#chatOptions summary').click();await page.locator('#q').fill(REVIEW)
        await page.locator('#cat').select_option('Smartphones')
        async def delayed(route):await asyncio.sleep(.5);await route.continue_()
        await page.route('**/api/chat',delayed)
        async with page.expect_response('**/api/chat') as pending:
            await page.locator('#q').press('Enter')
            await expect(page.locator('#send')).to_be_disabled();await expect(page.locator('#loading')).to_be_visible()
        response=await pending.value;data=await response.json()
        assert response.status==200 and data['model_version']=='phase3-full-logistic_regression-seed42'
        assert {a['aspect']:a['sentiment'] for a in data['aspects']}=={'battery':'positive','display':'positive','camera':'negative'}
        first_id=data['request_id']
        await expect(page.locator('#send')).to_be_enabled();await expect(page.locator('.sentiment')).to_have_text(data['sentiment'].title())
        assert not await page.locator('.analysis-about').evaluate('e => e.open')
        await page.locator('.analysis-about summary').click();await expect(page.locator('.analysis-about')).to_contain_text(data['model_version'])
        await page.locator('.analysis-about summary').click();await page.unroute('**/api/chat',delayed)
        checks.extend(['real_model_and_reported_aspect_regression','keyboard_submission_loading_and_duplicate_analysis_guard','technical_details_collapsed'])
        await page.locator('#q').fill('Why did you classify that review as positive?')
        async with page.expect_response('**/api/chat') as pending:await page.locator('#send').click()
        explanation=await (await pending.value).json()
        assert explanation['intent']=='explanation' and explanation['provider_status']=='consent_required'
        assert (await pending.value).request.post_data_json['analysis_request_id']==first_id
        checks.append('grounded_followup_uses_current_chat_prediction')
        await page.locator('.prediction-feedback').click();await expect(page.locator('#sendFb')).to_be_in_viewport()
        await expect(page.locator('#sendFb')).to_have_text('Submit Feedback')
        await expect(page.locator('#mclose')).to_be_focused();await page.keyboard.press('Tab')
        await expect(page.locator('#feedbackRating')).to_be_focused()
        await page.locator('#sendFb').click();assert await page.locator('#feedbackRating').evaluate('e => !e.validity.valid')
        await page.locator('#feedbackRating').select_option('4');await page.locator('#feedbackMessage').fill('Automated isolated UX persistence check')
        await page.locator('#feedbackConsent').check();await page.locator('#mclose').click()
        await page.locator('.prediction-feedback').click();await expect(page.locator('#feedbackMessage')).to_have_value('Automated isolated UX persistence check')
        checks.append('feedback_required_fields_and_draft_survives_reopen')
        async def unavailable(route):await route.fulfill(status=503,json={'error':{'message':'internal stack trace must not be displayed'}})
        await page.route('**/api/feedback',unavailable);await page.locator('#sendFb').click()
        await expect(page.locator('#feedbackStatus')).to_contain_text('temporarily unavailable')
        assert 'saved' not in await page.locator('#feedbackStatus').inner_text()
        await page.unroute('**/api/feedback',unavailable)
        checks.append('feedback_error_does_not_claim_storage')
        await page.route('**/api/feedback',delayed)
        async with page.expect_response('**/api/feedback') as pending:
            await page.locator('#sendFb').click();await expect(page.locator('#sendFb')).to_be_disabled()
        response=await pending.value;receipt=await response.json()
        assert response.status==201 and receipt['status']=='stored'
        await expect(page.locator('#feedbackStatus')).to_contain_text('Feedback saved')
        assert stored(receipt['feedback_id'])['request_id']==first_id
        await expect(page.locator('#sendFb')).to_be_disabled()
        await page.unroute('**/api/feedback',delayed)
        await page.locator('#mclose').click();await page.locator('.prediction-feedback').click()
        await expect(page.locator('#sendFb')).to_be_disabled();await expect(page.locator('#feedbackStatus')).to_contain_text('Feedback saved')
        checks.extend(['feedback_real_backend_database_persistence','feedback_duplicate_guard_and_receipt_survives_reopen'])
        for width,height in [(1440,640),(768,700),(390,640),(320,568)]:
            await page.set_viewport_size({'width':width,'height':height})
            await expect(page.locator('#sendFb')).to_be_in_viewport()
            box=await page.locator('#sendFb').bounding_box();assert box['y']>=0 and box['y']+box['height']<=height
            assert await page.locator('.dialog-body').first.evaluate('e => e.scrollHeight >= e.clientHeight')
            assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        checks.append('sticky_submit_visible_desktop_tablet_and_320px_mobile')
        await page.locator('#deleteFeedback').click();await expect(page.locator('#feedbackStatus')).to_have_text('Feedback deleted.')
        assert stored(receipt['feedback_id']) is None
        await page.locator('#mclose').click();await page.set_viewport_size({'width':1440,'height':1000})
        checks.append('delete_only_own_test_feedback')
        # Select a different result, then reopen the first to verify prediction association.
        await page.locator('#q').fill('The performance is good but the battery is poor.')
        async with page.expect_response('**/api/chat'):await page.locator('#send').click()
        await expect(page.locator('.prediction-feedback')).to_have_count(2)
        await page.locator('.prediction-feedback').first.click();await expect(page.locator('#feedbackTarget')).to_contain_text(first_id[:8])
        await page.locator('#mclose').click()
        checks.append('feedback_targets_selected_prediction_not_latest_result')
        await page.locator('#settingsBtn').click();await page.locator('#remember').check();await page.locator('#closeSettings').click()
        await page.reload(wait_until='networkidle');assert await page.locator('.msg.user').count()==3
        checks.append('opt_in_legacy_compatible_history_survives_refresh')
        await page.locator('#chatOptions summary').click();await page.locator('#cat').select_option('Smartphones')
        for language,review in [('hi','बैटरी अच्छी है।'),('hinglish','battery acha hai but camera poor')]:
            await page.locator('#lang').select_option(language);await page.locator('#q').fill(review)
            async with page.expect_response('**/api/chat') as pending:await page.locator('#send').click()
            result=await (await pending.value).json();assert any('accuracy is not established' in w for w in result['warnings'])
            await expect(page.locator('#send')).to_be_enabled()
        checks.append('hindi_hinglish_input_real_inference_with_limitations')
        await page.locator('#lang').select_option('en')
        async def fail(route):await route.fulfill(status=503,json={'error':{'message':'sensitive backend stack'}})
        await page.route('**/api/chat',fail);await page.locator('#q').fill('The screen is good.')
        await page.locator('#send').click();await expect(page.locator('.retry')).to_be_visible()
        await expect(page.locator('.error-card')).to_contain_text('temporarily unavailable')
        assert 'sensitive' not in await page.locator('#chat').inner_text()
        await expect(page.locator('#q')).to_have_value('The screen is good.')
        users_before=await page.locator('.msg.user').count()
        await page.unroute('**/api/chat',fail)
        async with page.expect_response('**/api/chat'):await page.locator('.retry').click()
        assert await page.locator('.msg.user').count()==users_before
        await expect(page.locator('#send')).to_be_enabled()
        checks.append('unavailable_backend_safe_error_and_working_retry')
        async def invalid(route):await route.fulfill(status=200,json={'type':'analysis','sentiment':'invented'})
        await page.route('**/api/chat',invalid);await page.locator('#q').fill('The phone works well.');await page.locator('#send').click()
        await expect(page.locator('.error-card').last).to_contain_text('unsupported analysis format')
        await page.unroute('**/api/chat',invalid)
        async def limited(route):await route.fulfill(status=429,json={'error':{'message':'limited'}})
        await page.route('**/api/chat',limited);await page.locator('#q').fill('The phone works well.');await page.locator('#send').click()
        await expect(page.locator('.error-card').last).to_contain_text('Wait one minute')
        await page.unroute('**/api/chat',limited)
        async def offline(route):await route.abort('internetdisconnected')
        await page.route('**/api/chat',offline);await page.locator('#q').fill('The phone works well.');await page.locator('#send').click()
        await expect(page.locator('.error-card').last).to_contain_text('Cannot reach the service')
        await page.unroute('**/api/chat',offline)
        checks.extend(['invalid_api_response_no_fabricated_fallback','rate_limit_message','network_error_message'])
        async def quota(route):await route.fulfill(status=429,json={'error':{'code':'provider_rate_limited','message':'private provider body'}})
        await page.route('**/api/chat',quota);await page.locator('#q').fill('The battery is good.');await page.locator('#send').click()
        await expect(page.locator('.error-card').last).to_contain_text('Google reported a Gemini quota or rate limit')
        await expect(page.locator('#q')).to_have_value('The battery is good.')
        await page.unroute('**/api/chat',quota)
        checks.append('specific_provider_quota_error_preserves_message_and_retry')
        async def waiting(route):
            await asyncio.sleep(1)
            try:await route.abort()
            except Exception:pass  # The timeout may have already cancelled this request.
        await page.clock.install()
        await page.route('**/api/chat',waiting);await page.locator('#q').fill('The phone works well.');await page.locator('#send').click()
        await expect(page.locator('#loading')).to_be_visible()
        await page.clock.fast_forward(46000)
        await expect(page.locator('.error-card').last).to_contain_text('took too long')
        await page.unroute('**/api/chat',waiting);await page.clock.resume()
        checks.append('timeout_and_waking_service_message')
        await page.locator('#q').evaluate('e => e.value = "x".repeat(5001)');await page.locator('#send').click()
        await expect(page.locator('#hint')).to_contain_text('5,000')
        await page.locator('#q').fill('<img src=x onerror=alert(1)> The battery is good.')
        async with page.expect_response('**/api/chat'):await page.locator('#send').click()
        await expect(page.locator('#send')).to_be_enabled();assert await page.locator('.msg.user img').count()==0 and not dialogs
        checks.append('length_validation_and_review_html_escaping')
        await page.locator('#cat').select_option('Other tech');await page.locator('#q').fill('The product works well.')
        async with page.expect_response('**/api/chat'):await page.locator('#send').click()
        await expect(page.locator('.card').last).to_contain_text('No matching product features')
        checks.append('unsupported_category_honest_no_aspects_state')
        await page.locator('#settingsBtn').click();await page.locator('#clearHist').click();await page.locator('#closeSettings').click()
        assert await page.evaluate('localStorage.getItem("reviewmind_guest_history_v1")') is None
        await page.reload(wait_until='networkidle');await expect(page.locator('#welcome')).to_be_visible()
        checks.append('clear_history_removes_only_device_and_session_history')
        # Final evidence uses one real prediction and no injected result fixtures.
        await page.locator('#chatOptions summary').click()
        await page.locator('#cat').select_option('Smartphones');await page.locator('#q').fill(REVIEW)
        async with page.expect_response('**/api/chat'):await page.locator('#send').click()
        await expect(page.locator('.prediction-feedback')).to_be_visible()
        await page.locator('#chatOptions summary').click()
        await page.evaluate('scrollTo(0,0)')
        figures=ROOT/'reports/figures';figures.mkdir(exist_ok=True)
        await page.screenshot(path=str(figures/'phase3_5_agent_desktop.png'),full_page=True,animations='disabled')
        await page.locator('.prediction-feedback').click();await page.set_viewport_size({'width':390,'height':720})
        await expect(page.locator('#sendFb')).to_be_in_viewport()
        await page.screenshot(path=str(figures/'phase3_5_agent_feedback_mobile.png'),animations='disabled')
        await page.keyboard.press('Escape');await expect(page.locator('#modal')).to_be_hidden()
        await expect(page.locator('.prediction-feedback')).to_be_focused()
        await page.locator('#themeBtn').click();assert await page.locator('html').get_attribute('data-theme')=='dark'
        await page.evaluate('scrollTo(0,0)');assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        await page.screenshot(path=str(figures/'phase3_5_agent_mobile.png'),full_page=True,animations='disabled')
        checks.extend(['feedback_escape_and_keyboard_focus','responsive_mobile_dark_theme'])
        assert not errors,errors
        await browser.close()
    if database_url.startswith('postgresql'):
        with db.engine.connect() as c:assert c.execute(text('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()')).scalar() is True
        checks.append('feedback_database_is_real_tls_postgresql')
    db.engine.dispose()
    report={'status':'passed','workflows_passed':len(checks),'checks':checks,'unhandled_browser_errors':errors,
      'database':'TLS PostgreSQL' if database_url.startswith('postgresql') else 'SQLite',
      'error_fixtures':'Error paths intercepted; all successful predictions and feedback use the actual backend.',
      'screenshots':['reports/figures/phase3_5_agent_desktop.png','reports/figures/phase3_5_agent_feedback_mobile.png','reports/figures/phase3_5_agent_mobile.png']}
    (ROOT/'reports/phase3_5_agent_browser.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Browser workflows passed:',len(checks))

if __name__=='__main__':asyncio.run(run())
