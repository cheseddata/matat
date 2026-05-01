"""Microsoft Graph inbox provider (Office 365 / Exchange Online).

Authenticates via OAuth client_credentials with `Mail.Read` application
permission against the tenant — the server gets its own access token
without a user signing in. The token grants Mail.Read across the
tenant; we only ever call it against the single mailbox stored on the
provider row, so a mis-typed mailbox can't accidentally read someone
else's mail.

config_json shape:
  {
    'tenant_id':     '37c84bb0-...',
    'client_id':     '0d08088e-...',
    'client_secret': 'Mfq8Q~...',
  }
"""
import logging
import requests

from .base import BaseInboxProvider

logger = logging.getLogger(__name__)

GRAPH_BASE_URL = 'https://graph.microsoft.com/v1.0'
GRAPH_SCOPE = 'https://graph.microsoft.com/.default'


class MicrosoftGraphInbox(BaseInboxProvider):
    code = 'msgraph'
    name = 'Microsoft Graph (Office 365 / Exchange Online)'

    def _required_keys(self):
        return ('tenant_id', 'client_id', 'client_secret')

    def _missing_config(self):
        return [k for k in self._required_keys() if not self.config.get(k)]

    def _mailbox(self):
        return self.provider.mailbox_address

    def _get_access_token(self):
        missing = self._missing_config()
        if missing:
            return {'error': f'Missing config keys: {", ".join(missing)}'}
        tenant_id = self.config['tenant_id']
        token_url = f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token'
        body = {
            'client_id':     self.config['client_id'],
            'client_secret': self.config['client_secret'],
            'scope':         GRAPH_SCOPE,
            'grant_type':    'client_credentials',
        }
        try:
            r = requests.post(token_url, data=body, timeout=15)
        except requests.exceptions.RequestException as e:
            return {'error': f'Network error fetching token: {e}'}

        if r.status_code != 200:
            try:
                err = r.json()
                return {'error': f'{err.get("error")}: {err.get("error_description")}'}
            except ValueError:
                return {'error': f'HTTP {r.status_code}: {r.text[:300]}'}
        return {'access_token': r.json().get('access_token')}

    def test_connection(self):
        if not self._mailbox():
            return {'success': False, 'error': 'No mailbox_address set on this provider.'}

        token_resp = self._get_access_token()
        if 'error' in token_resp:
            return {'success': False, 'error': f'Auth failed: {token_resp["error"]}'}

        headers = {'Authorization': f'Bearer {token_resp["access_token"]}'}
        url = f'{GRAPH_BASE_URL}/users/{self._mailbox()}'
        try:
            r = requests.get(url, headers=headers, timeout=15)
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': f'Mailbox lookup network error: {e}'}

        if r.status_code == 200:
            u = r.json()
            return {
                'success':      True,
                'mailbox':      u.get('mail') or u.get('userPrincipalName'),
                'display_name': u.get('displayName'),
                'user_id':      u.get('id'),
                'message':      'Authenticated and mailbox is reachable.',
            }
        if r.status_code == 404:
            return {'success': False, 'error': f'Mailbox "{self._mailbox()}" not found in this tenant.'}
        if r.status_code == 403:
            return {'success': False, 'error': 'Authenticated but no permission for this mailbox. Verify Mail.Read admin consent or any Application Access Policy scoping.'}

        try:
            err = r.json()
            return {'success': False, 'error': f'Graph error {r.status_code}: {err.get("error", {}).get("message", r.text[:300])}'}
        except ValueError:
            return {'success': False, 'error': f'HTTP {r.status_code}: {r.text[:300]}'}

    def fetch_new_messages(self, limit=100):
        # Phase 2 — implementation to come. Returns empty for now so
        # the sync command no-ops cleanly when wired up.
        return []
