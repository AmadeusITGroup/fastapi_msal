from typing import Optional, Dict
from fastapi import Request, HTTPException, status
from fastapi.openapi.models import OAuth2 as OAuth2Model, OAuthFlowAuthorizationCode
from fastapi.security.base import SecurityBase
from fastapi.openapi.models import OAuthFlows as OAuthFlowsModel, SecuritySchemeType
from fastapi.security.utils import get_authorization_scheme_param

from fastapi_msal.models import IDTokenClaims
from .msal_auth_code_handler import MSALAuthCodeHandler


class MSALScheme(SecurityBase):
    def __init__(
        self,
        authorizationUrl: str,
        tokenUrl: str,
        handler: MSALAuthCodeHandler,
        required_role: Optional[str] = None,
        refreshUrl: Optional[str] = None,
        scopes: Optional[Dict[str, str]] = None,
    ):
        self.required_role = required_role
        self.handler = handler
        if not scopes:
            scopes = {}
        self.scheme_name = self.__class__.__name__

        flows = OAuthFlowsModel(
            authorizationCode=OAuthFlowAuthorizationCode(
                authorizationUrl=authorizationUrl,
                tokenUrl=tokenUrl,
                scopes=scopes,
                refreshUrl=refreshUrl,
            )
        )
        # needs further investigation (type...)
        self.model = OAuth2Model(flows=flows, type=SecuritySchemeType.oauth2)

    async def __call__(self, request: Request) -> IDTokenClaims:
        http_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
        authorization: str = request.headers.get("Authorization")
        scheme, token = get_authorization_scheme_param(authorization)
        if not authorization or scheme.lower() != "bearer":
            raise http_exception
        token_claims: Optional[IDTokenClaims] = await self.handler.parse_id_token(
            request=request, token=token, validate=True
        )
        if not token_claims:
            raise http_exception
        if self.required_role:
            if not self.authorized(token_claims):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized",
                    headers={"WWW-Authenticate": "Bearer"},)
        return token_claims

    def authorized(self, token_claims: IDTokenClaims) -> bool:
        # should we also check the scope?
        is_authorized = token_claims.roles and self.required_role in token_claims.roles
        return is_authorized
