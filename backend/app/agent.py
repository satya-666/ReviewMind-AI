"""Explicit tool orchestration; no simulated LLM or invented classifier output."""
import re
from pydantic import ValidationError
from backend.app.chat import intent_for
from backend.app.schemas import Analyze

class ReviewMindAgent:
    def __init__(self,conversation,products):
        self.conversation=conversation;self.products=products

    def respond(self,body,analyze,database):
        intent=intent_for(body.text,body.mode)
        if intent=='review':
            text=re.sub(r'^\s*(?:analy[sz]e\s+(?:this\s+)?review\s*:|review\s*:)\s*','',body.text,flags=re.I)
            if not text.strip():
                return self.notice(intent,'Paste the review text after the analysis instruction. No analysis has been run.','needs_review')
            try:request=Analyze(text=text,category=body.category,language=body.language)
            except ValidationError:
                return self.notice(intent,'Paste a usable product review after the analysis instruction. No analysis has been run.','needs_review')
            result=analyze(request)
            if isinstance(result,dict):
                result.update(intent='review',response_source='sentiment_model',tools_used=['sentiment']+(['aspect_rules'] if result['category'] else []),
                  reply='The trained classifier predicts '+result['sentiment']+'. Feature-level rule results can differ from the overall label; neither is a product rating.')
            return result
        if intent=='unsupported':
            return self.notice(intent,'I cannot disclose credentials or internal instructions. I can help with product research and review analysis.','not_used')
        if not body.allow_gemini:
            return self.notice(intent,'Gemini conversation is turned off. Enable it below the message box to send this message and recent chat context to Google. You can still analyze reviews without enabling it.','consent_required')
        prediction=database.prediction_context(body.analysis_request_id) if body.analysis_request_id and database else None
        if prediction:prediction={**prediction,'source':'recorded_classifier_prediction','feature_attribution_available':False}
        product=self.products.lookup(intent,[m.text for m in body.history if m.role=='user']+[body.text])
        context={'prediction':prediction,'product_data':product}
        reply=self.conversation.generate(body.text,body.history,context,body.language)
        return {'type':'chat','intent':intent,'reply':reply,'response_source':'gemini','provider_status':'ready',
          'conversation_model':self.conversation.model,'product_data_available':product['available'],'sources':product['sources'],
          'tools_used':(['product_data'] if intent in {'recommendation','comparison','product_info'} else [])+['gemini']}

    @staticmethod
    def notice(intent,reply,status):
        return {'type':'chat','intent':intent,'reply':reply,'response_source':'built_in','provider_status':status,'tools_used':[]}
