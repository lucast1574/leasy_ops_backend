"""
Google OAuth helpers — shared by mobile (id_token flow) and backoffice (auth code flow).

Extracted from the old monolithic users/views.py as part of the module split.
Logic is byte-identical — only the surrounding imports were adjusted for the new
module location (and the leading underscore was dropped from public helpers).
"""
import os
import logging
import requests as http_requests

logger = logging.getLogger(__name__)

GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
GOOGLE_WEB_CLIENT_ID = os.environ.get('GOOGLE_WEB_CLIENT_ID', '')
GOOGLE_ANDROID_CLIENT_ID = os.environ.get('GOOGLE_ANDROID_CLIENT_ID', '')
VALID_CLIENT_IDS = [cid for cid in [GOOGLE_CLIENT_ID, GOOGLE_WEB_CLIENT_ID, GOOGLE_ANDROID_CLIENT_ID] if cid]

DOMAIN_TO_COUNTRY = {
    'leasyauto.com': 'PE',
    'floty.mx': 'MX',
}

BACKOFFICE_CLIENT_ID = GOOGLE_WEB_CLIENT_ID or GOOGLE_CLIENT_ID
BACKOFFICE_CLIENT_SECRET = os.environ.get('GOOGLE_WEB_CLIENT_SECRET', '') or GOOGLE_CLIENT_SECRET


def get_email_from_id_token(token_str):
    import base64, json as _json
    parts = token_str.split('.')
    if len(parts) != 3:
        raise ValueError('Malformed id_token')
    payload_b64 = parts[1] + '=' * (4 - len(parts[1]) % 4)
    try:
        idinfo = _json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception as e:
        raise ValueError(f'Failed to decode id_token: {e}')
    token_aud = idinfo.get('aud', '')
    if token_aud not in VALID_CLIENT_IDS:
        raise ValueError(f'Token audience {token_aud} not in valid client IDs')
    return {
        'email': idinfo.get('email', '').lower(),
        'first_name': idinfo.get('given_name', ''),
        'last_name': idinfo.get('family_name', ''),
        'picture': idinfo.get('picture', ''),
    }


def get_email_from_auth_code(code):
    exchange_client_id = BACKOFFICE_CLIENT_ID
    exchange_client_secret = BACKOFFICE_CLIENT_SECRET
    logger.info(f'[OAUTH] Starting code exchange with client_id={exchange_client_id[:20]}...')
    try:
        token_resp = http_requests.post('https://oauth2.googleapis.com/token', data={
            'code': code,
            'client_id': exchange_client_id,
            'client_secret': exchange_client_secret,
            'redirect_uri': 'postmessage',
            'grant_type': 'authorization_code',
        }, timeout=15)
        logger.info(f'[OAUTH] Google token response: status={token_resp.status_code}')
    except http_requests.exceptions.Timeout:
        logger.error('[OAUTH] Timeout calling Google token endpoint')
        raise ValueError('Google token exchange timed out after 15s')
    except http_requests.exceptions.ConnectionError as e:
        logger.error(f'[OAUTH] Connection error: {e}')
        raise ValueError(f'Cannot connect to Google: {e}')
    if token_resp.status_code != 200:
        raise ValueError(f'Failed to exchange code: {token_resp.text}')

    token_data = token_resp.json()
    id_token_str = token_data.get('id_token')
    if not id_token_str:
        raise ValueError('No id_token in response')

    import base64, json as _json
    parts = id_token_str.split('.')
    if len(parts) != 3:
        raise ValueError('Malformed id_token')
    payload_b64 = parts[1] + '=' * (4 - len(parts[1]) % 4)
    try:
        idinfo = _json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception as e:
        raise ValueError(f'Failed to decode id_token: {e}')
    logger.info(f'[OAUTH] Token decoded, email={idinfo.get("email","?")}')
    return {
        'email': idinfo.get('email', '').lower(),
        'first_name': idinfo.get('given_name', ''),
        'last_name': idinfo.get('family_name', ''),
        'picture': idinfo.get('picture', ''),
    }
