"""Real browser workflows against a running local beta API. No model predictions mocked."""
import asyncio,json,os,time
from pathlib import Path
from playwright.async_api import async_playwright,expect

ROOT=Path(__file__).resolve().parents[1]

async def run():
    base=os.getenv('WEB_TEST_URL','http://127.0.0.1:8765')
    checks=[];errors=[];dialogs=[]
    async with async_playwright() as playwright:
        browser=await playwright.chromium.launch(headless=True)
        context=await browser.new_context(viewport={'width':1440,'height':1000})
        page=await context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('dialog',lambda dialog:dialogs.append(dialog.message))
        await page.goto(base,wait_until='networkidle')
        await expect(page.locator('.brand b')).to_have_text('ReviewMind AI')
        assert await page.locator('body').evaluate('e => getComputedStyle(e).backgroundColor')=='rgb(243, 237, 255)'
        checks.append('provided_frontend_loads_with_original_light_palette')
        await page.locator('#cat').select_option(label='Smartphones')
        async def delayed(route):
            await asyncio.sleep(.5);await route.continue_()
        await page.route('**/api/analyze',delayed)
        await page.locator('#q').fill('The camera is excellent, but the battery drains quickly.')
        async with page.expect_response('**/api/analyze') as pending:
            await page.locator('#send').click()
            await expect(page.locator('#send')).to_be_disabled()
            await expect(page.locator('[aria-label="Loading"]')).to_be_visible()
        response=await pending.value;data=await response.json()
        assert response.status==200 and data['model_version'].startswith('phase3-full-logistic_regression')
        await expect(page.locator('.prediction-feedback').last).to_be_visible()
        await expect(page.locator('#send')).to_be_enabled()
        await expect(page.get_by_text('Overall sentiment:',exact=False)).to_be_visible()
        assert any(a['name']=='Camera' and a['sentiment']=='positive' for a in data['aspects'])
        assert any(a['name']=='Battery' and a['sentiment']=='negative' for a in data['aspects'])
        checks.extend(['real_english_inference_and_aspects','loading_and_disabled_send'])
        await page.unroute('**/api/analyze',delayed)
        for language,text in [('hi','बैटरी अच्छी है।'),('hinglish','battery acha hai but sound poor')]:
            await page.locator('#lang').select_option(language)
            await page.locator('#q').fill(text)
            async with page.expect_response('**/api/analyze') as pending:await page.locator('#send').click()
            result=await (await pending.value).json()
            assert result['sentiment'] in ['positive','neutral','negative']
            assert any('accuracy is not established' in warning for warning in result['warnings'])
            await expect(page.locator('#send')).to_be_enabled()
        checks.extend(['hindi_input_with_accuracy_warning','hinglish_input_with_accuracy_warning','language_switching'])
        await page.locator('#lang').select_option('en')
        await page.locator('.prediction-feedback').last.click()
        await page.locator('#feedbackRating').select_option('4')
        await page.locator('#feedbackCorrection').select_option('neutral')
        await page.locator('#feedbackMessage').fill('Synthetic browser integration feedback')
        await page.locator('#feedbackConsent').check()
        async with page.expect_response('**/api/feedback') as pending:await page.locator('#sendFb').click()
        stored=await (await pending.value).json();assert stored['status']=='stored'
        await expect(page.locator('#feedbackStatus')).to_contain_text('stored successfully')
        # Independent DB connection verifies server-confirmed storage, not a UI-only toast.
        import sys
        sys.path.insert(0,str(ROOT))
        from sqlalchemy import create_engine,select
        from backend.app.db import Feedback
        engine=create_engine('sqlite:///'+str(ROOT/'.cache/web/e2e-feedback.db'))
        with engine.connect() as connection:assert connection.execute(select(Feedback.rating).where(Feedback.id==stored['feedback_id'])).scalar()==4
        checks.append('real_feedback_submission_and_persistent_database_row')
        await page.locator('#deleteFeedback').click()
        await expect(page.locator('#feedbackStatus')).to_have_text('Feedback deleted.')
        checks.append('feedback_deletion_with_opaque_token')
        await page.locator('.mtabs [data-tab="settings"]').click()
        await page.locator('#remember').check();await page.locator('#mclose').click()
        await page.reload(wait_until='networkidle')
        await expect(page.locator('.msg.user').first).to_contain_text('The camera is excellent')
        checks.append('opt_in_guest_history_survives_refresh_without_saved_html')
        await page.locator('#task').select_option('auto')
        await page.locator('#q').fill('Best smartphone under 20000')
        async with page.expect_response('**/api/recommend') as pending:await page.locator('#send').click()
        unavailable=await (await pending.value).json();assert unavailable['status']=='not_available' and unavailable['products']==[]
        await expect(page.get_by_text('Product intelligence · upcoming')).to_be_visible()
        assert await page.locator('.card.top').count()==0
        checks.extend(['automatic_product_question_routing','unsupported_recommendations_render_without_fabricated_cards'])
        await page.locator('#task').select_option('analyze')
        async def bad_model(route):await route.fulfill(status=503,content_type='application/json',body=json.dumps({'error':{'message':'Model temporarily unavailable.'}}))
        async def bad_format(route):await route.fulfill(status=200,content_type='application/json',body='{"sentiment":"mixed"}')
        async def limited(route):await route.fulfill(status=429,content_type='application/json',body='{}')
        async def offline(route):await route.abort('failed')
        for handler,expected in [(bad_model,'Model temporarily unavailable'),(bad_format,'unsupported analysis format'),(limited,'Rate limit reached'),(offline,'Cannot reach the API')]:
            await page.route('**/api/analyze',handler)
            await page.locator('#q').fill('Another battery review')
            await page.locator('#send').click()
            await expect(page.locator('.bubble.err').last).to_contain_text(expected)
            await expect(page.locator('#send')).to_be_enabled()
            await page.unroute('**/api/analyze',handler)
        checks.extend(['model_unavailable_ui','invalid_response_ui','rate_limit_ui','network_error_ui_no_fake_fallback'])
        await page.locator('#q').fill('   ');await page.locator('#send').click()
        await expect(page.locator('#hint')).to_contain_text('between 1 and 5,000')
        checks.append('empty_input_validation')
        await page.locator('#q').fill('<img src=x onerror="alert(1)"> battery good')
        async with page.expect_response('**/api/analyze'):await page.locator('#send').click()
        await expect(page.locator('#send')).to_be_enabled()
        assert await page.locator('.msg.user img').count()==0 and not dialogs
        checks.append('user_review_html_is_escaped')
        await page.locator('#themeBtn').click()
        assert await page.locator('html').get_attribute('data-theme')=='dark'
        checks.append('dark_mode')
        figures=ROOT/'reports/figures';figures.mkdir(exist_ok=True)
        await page.screenshot(path=str(figures/'phase3_5_desktop.png'),full_page=False)
        await page.set_viewport_size({'width':390,'height':844})
        assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        await page.locator('#menuBtn').click();await expect(page.locator('#side')).to_have_class('open')
        await page.locator('#closeSide').click()
        await page.screenshot(path=str(figures/'phase3_5_mobile.png'),full_page=False)
        checks.append('mobile_layout_and_sidebar')
        await page.locator('#menuBtn').click();await page.locator('#pbtn').click()
        await page.locator('.pmenu [data-open="upgrade"]').click()
        assert await page.locator('[data-plan="plus"]').is_disabled()
        await page.locator('.mtabs [data-tab="settings"]').click();await page.locator('#clearHist').click();await page.locator('#mclose').click()
        assert await page.evaluate('localStorage.getItem("reviewmind_guest_history_v1")') is None
        await page.reload(wait_until='networkidle');assert await page.locator('.msg.user').count()==0
        checks.extend(['billing_disabled_guest_only','clear_history_removes_persistent_review_text'])
        # Publish clean, actual-analysis screenshots rather than the intentional error-state exercises.
        await page.set_viewport_size({'width':1440,'height':1000})
        await page.locator('#prefs summary').click()
        await page.locator('#task').select_option('analyze');await page.locator('#cat').select_option('Smartphones')
        await page.locator('#q').fill('The camera is excellent, but the battery drains quickly.')
        async with page.expect_response('**/api/analyze'):await page.locator('#send').click()
        await expect(page.locator('.prediction-feedback')).to_be_visible()
        await page.locator('#prefs summary').click()
        await page.locator('#scroll').evaluate('e => e.scrollTop = 0')
        await page.screenshot(path=str(figures/'phase3_5_desktop.png'),full_page=False,animations='disabled')
        await page.locator('#themeBtn').click();await page.set_viewport_size({'width':390,'height':844})
        await page.keyboard.press('Escape')
        await expect(page.locator('#side')).not_to_have_class('open')
        assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        await page.screenshot(path=str(figures/'phase3_5_mobile.png'),full_page=False,animations='disabled')
        assert not errors,errors
        await browser.close()
    report={'status':'passed','workflows_passed':len(checks),'checks':checks,'unhandled_browser_errors':errors,
      'error_fixtures':'Unavailable/invalid/rate-limited/offline responses intentionally intercepted to test UI error paths; model prediction workflows use the real backend.',
      'screenshots':['reports/figures/phase3_5_desktop.png','reports/figures/phase3_5_mobile.png']}
    (ROOT/'reports/phase3_5_browser.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Browser workflows passed:',len(checks))

if __name__=='__main__':asyncio.run(run())
