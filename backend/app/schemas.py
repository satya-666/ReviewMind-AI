"""Strict bounded inputs. Client-provided model metadata is never trusted for feedback."""
from typing import Literal
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field,field_validator

Label=Literal['negative','neutral','positive']
class Strict(BaseModel):model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)

class Analyze(Strict):
    text:str=Field(min_length=1,max_length=5000)
    category:str|None=Field(default=None,max_length=64)
    language:Literal['en','hi','hinglish','english','hindi','other_indic','other','unknown']='en'
    @field_validator('text')
    @classmethod
    def usable_text(cls,value):
        from scripts.clean_data import clean_text,usable
        if not usable(clean_text(value)):raise ValueError('A usable review is required')
        return value

class Preferences(Strict):
    category:str=Field(default='',max_length=64)
    budget:int|None=Field(default=None,ge=0,le=10000000)
    priorities:list[str]=Field(default_factory=list,max_length=12)
    language:str=Field(default='en',max_length=16)
    style:str=Field(default='friendly',max_length=24)
    user_name:str=Field(default='Guest',max_length=40)
    @field_validator('priorities')
    @classmethod
    def bounded_priorities(cls,value):
        if any(len(item)>64 for item in value):raise ValueError('Priority too long')
        return value

class Recommend(Strict):
    query:str=Field(min_length=1,max_length=5000)
    preferences:Preferences=Field(default_factory=Preferences)

class FeedbackInput(Strict):
    request_id:UUID
    rating:int=Field(ge=1,le=5,strict=True)
    correction:Label|None=None
    message:str|None=Field(default=None,max_length=1000)
    consent:Literal[True]

class ChatMessage(Strict):
    role:Literal['user','assistant']
    text:str=Field(min_length=1,max_length=1000)

class ChatInput(Analyze):
    history:list[ChatMessage]=Field(default_factory=list,max_length=8)
    analysis_request_id:UUID|None=None
    mode:Literal['auto','review']='auto'
    allow_gemini:bool=False

    @field_validator('history')
    @classmethod
    def bounded_context(cls,value):
        if sum(len(m.text) for m in value)>4000:raise ValueError('Conversation context too long')
        return value
