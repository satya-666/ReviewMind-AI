"""Explicit tool orchestration; no simulated LLM or invented classifier output."""
import re
from backend.app.products import budget_from,brand_from
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
            return self.notice(intent,'Gemini conversation is turned off. Enable third-party conversation in Settings to send this message and recent chat context to Google. You can still analyze reviews without enabling it.','consent_required')
        prediction=database.prediction_context(body.analysis_request_id) if body.analysis_request_id and database else None
        if prediction:prediction={**prediction,'source':'recorded_classifier_prediction','feature_attribution_available':False}
        product=self.products.lookup(intent,[m.text for m in body.history if m.role=='user']+[body.text])
        context={'prediction':prediction,'product_data':product}
        used=[];analysis_result=None;searched=False
        messages=[m.text for m in body.history if m.role=='user']+[body.text]
        budget=budget_from(messages)
        def execute(name,args):
            nonlocal analysis_result,searched
            if not isinstance(args,dict):return {'error':'invalid_arguments'}
            if name in {'product_search','product_details','product_comparison'}:
                if not body.allow_product_search or not self.products.configured:return {'error':'Product retrieval requires consent and configuration.'}
                if searched:return {'error':'Only one retrieval per turn; compare the returned listings.'}
                searched=True
                query=args.get('query');brand=brand_from(messages) or args.get('brand')
                if brand and (not isinstance(brand,str) or len(brand)>60 or brand.casefold() not in ' '.join(messages).casefold()):return {'error':'Brand must come from user preferences.'}
                product=self.products.search(query,budget,brand)
                context['product_data']=product;used.append(name)
                return product
            if name in {'sentiment_analysis','aspect_detection'}:
                text=args.get('text');category=args.get('category') or body.category
                if not isinstance(text,str) or not text.strip() or text not in body.text or intent_for(text)!='review':return {'error':'Only exact review text in the current message can be analyzed.'}
                if analysis_result is not None:return {'error':'Analysis already executed.'}
                try:request=Analyze(text=text,category=category,language=body.language)
                except ValidationError:return {'error':'Invalid review input.'}
                analysis_result=analyze(request)
                if not isinstance(analysis_result,dict):return {'error':'Analysis unavailable.'}
                used.extend(['sentiment','aspect_rules'] if analysis_result.get('category') else ['sentiment'])
                context['prediction']={'sentiment':analysis_result['sentiment'],'model_version':analysis_result['model_version'],'feature_attribution_available':False}
                return analysis_result
            return {'error':'Unknown tool.'}
        tools=[]
        for name in ['product_search','product_details','product_comparison']:
            tools.append({'name':name,'description':'Retrieve India shopping listings for '+name.replace('_',' ')+'. Returns only provider evidence; missing fields are unknown.',
              'parameters':{'type':'OBJECT','properties':{'query':{'type':'STRING'},'brand':{'type':'STRING'}},'required':['query']}})
        for name in ['sentiment_analysis','aspect_detection']:
            tools.append({'name':name,'description':'Run the existing trained sentiment classifier and category-specific lexical aspect rules on a real review.',
              'parameters':{'type':'OBJECT','properties':{'text':{'type':'STRING'},'category':{'type':'STRING'}},'required':['text']}})
        # Product tools are advertised only when configured; no simulated retrieval success.
        if not self.products.configured or not body.allow_product_search:tools=tools[3:]
        if tools:reply=self.conversation.generate(body.text,body.history,context,body.language,tools,execute)
        else:reply=self.conversation.generate(body.text,body.history,context,body.language)
        if isinstance(analysis_result,dict):
            return dict(analysis_result,reply='The trained classifier predicts '+analysis_result['sentiment']+'. Exact causal feature importance is unavailable. Aspect results use separate lexical rules.',response_source='sentiment_model',tools_used=used+['gemini'])
        product=context['product_data']
        return {'type':'chat','intent':intent,'reply':reply,'response_source':'gemini','provider_status':'ready',
          'conversation_model':self.conversation.model,'product_data_available':product['available'],'sources':product['sources'],
          'products':product['products'],'product_status':product.get('status','not_configured'),
          'tools_used':used+['gemini']}

    @staticmethod
    def notice(intent,reply,status):
        return {'type':'chat','intent':intent,'reply':reply,'response_source':'built_in','provider_status':status,'tools_used':[]}
