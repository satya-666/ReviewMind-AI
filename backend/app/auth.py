"""Verify Google's signed identity tokens; never store credentials or request Gmail access."""
from functools import partial
from cachecontrol import CacheControl
from requests import Session
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from google.auth.exceptions import TransportError,GoogleAuthError
from fastapi import HTTPException,Request as WebRequest

class GoogleAuth:
    def __init__(self,client_id,required):
        self.client_id=client_id;self.required=required
        self.session=CacheControl(Session())
        self.request=partial(Request(session=self.session),timeout=5)

    def verify(self,token):
        try:claims=id_token.verify_oauth2_token(token,self.request,self.client_id)
        except TransportError:
            raise HTTPException(503,detail='Sign-in verification is temporarily unavailable.') from None
        except (ValueError,TypeError,KeyError,GoogleAuthError):
            raise HTTPException(401,detail='Your sign-in expired or is invalid. Sign in again.') from None
        if not claims.get('sub') or claims.get('email_verified') is not True or not isinstance(claims.get('email'),str):
            raise HTTPException(401,detail='A verified Google email address is required.')
        return {'id':claims['sub'],'email':claims['email'],'expires_at':claims['exp']}

    def optional_user(self,request:WebRequest):
        return self.user(request) if request.headers.get("authorization") else None

    def user(self,request:WebRequest):
        if not self.required:return None
        if not self.client_id:raise HTTPException(503,detail='Google sign-in has not been configured yet.')
        scheme,_,token=request.headers.get('authorization','').partition(' ')
        if scheme.lower()!='bearer' or not token or len(token)>8192:
            raise HTTPException(401,detail='Sign in with Google to continue.')
        return self.verify(token)
