# services/jmx/oauth2.py
"""
JMeter OAuth 2.0 / OpenID Connect JMX element builders.

Creates JMX elements for OAuth token extraction and refresh flows.
Wraps the generic extractors in post_processor.py with OAuth-aware defaults.
"""
from typing import Dict, Optional, Tuple
import xml.etree.ElementTree as ET

from .post_processor import create_json_extractor


# Default JSONPath expressions for common OAuth token types.
# Callers can override by passing an explicit json_path argument.
TOKEN_TYPE_JSONPATHS: Dict[str, str] = {
    "access_token": "$.access_token",
    "id_token": "$.id_token",
    "refresh_token": "$.refresh_token",
    "token_type": "$.token_type",
    "expires_in": "$.expires_in",
    "scope": "$.scope",
    # SSO / ForgeRock / OpenAM tokens
    "cdssotoken": "$.tokenId",
    "sso_token": "$.tokenId",
    "tokenid": "$.tokenId",
}


def create_oauth_token_extractor(
    variable_name: str,
    json_path: Optional[str] = None,
    token_type: str = "access_token",
    default_value: str = "NOT_FOUND",
) -> ET.Element:
    """
    Creates a JSON Extractor element for extracting an OAuth token.

    Wraps create_json_extractor() with OAuth-specific defaults:
    - Derives json_path from token_type when not explicitly provided.
    - Sets a descriptive testname (e.g. "Extract OAuth access_token").
    - Uses NOT_FOUND as default so failures are immediately visible.

    Args:
        variable_name: JMeter variable to store the extracted value.
        json_path: JSONPath expression. If None, inferred from token_type
                   via TOKEN_TYPE_JSONPATHS (falls back to $.{token_type}).
        token_type: One of "access_token", "id_token", "refresh_token",
                    "cdssotoken", "sso_token", "tokenid", etc.
        default_value: Value when extraction fails (default "NOT_FOUND").

    Returns:
        ET.Element: JSONPostProcessor element ready for JMX hashTree insertion.
    """
    if json_path is None:
        json_path = TOKEN_TYPE_JSONPATHS.get(
            token_type, f"$.{token_type}"
        )

    testname = f"Extract OAuth {token_type}"

    return create_json_extractor(
        variable_name=variable_name,
        json_path=json_path,
        match_no="1",
        default_value=default_value,
        testname=testname,
    )

def create_oauth_refresh_flow(
    refresh_endpoint_url: str,
    client_id: str,
    current_token_var: str,
    refresh_token_var: str,
    output_var: str
) -> Tuple[ET.Element, ET.Element]:
    """
    Creates a POST sampler + extractors for calling an OAuth refresh endpoint.
    Returns (sampler, hash_tree) ready for JMX insertion.
    
    Future enhancement: wire in PKCE, grant types, token expiration logic.
    """
    # TODO: implement

# Additional helper functions and constants as needed