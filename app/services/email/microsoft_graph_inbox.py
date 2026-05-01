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

        # Probe a Mail.Read-only endpoint (one inbox message header) so
        # we don't accidentally fail because the app lacks User.Read.All.
        # /users/{mbx}/mailFolders/inbox/messages?$top=1 works with just
        # Mail.Read application permission.
        headers = {'Authorization': f'Bearer {token_resp["access_token"]}'}
        url = (f'{GRAPH_BASE_URL}/users/{self._mailbox()}'
               f'/mailFolders/inbox/messages?$top=1&$select=id,subject,receivedDateTime')
        try:
            r = requests.get(url, headers=headers, timeout=15)
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': f'Mailbox probe network error: {e}'}

        if r.status_code == 200:
            data = r.json() or {}
            messages = data.get('value') or []
            return {
                'success': True,
                'mailbox': self._mailbox(),
                'message': f'Authenticated, Mail.Read works. Inbox has at least one message: {bool(messages)}',
                'sample_subject': messages[0].get('subject') if messages else None,
            }
        if r.status_code == 404:
            return {'success': False, 'error': f'Mailbox "{self._mailbox()}" not found in this tenant. Check the address.'}
        if r.status_code == 403:
            try:
                err = r.json()
                graph_msg = err.get('error', {}).get('message', '')
            except ValueError:
                graph_msg = r.text[:300]
            return {'success': False, 'error': f'Forbidden — admin consent for Mail.Read may not have propagated yet (5-15 min), or an Application Access Policy is scoping us out. Graph said: {graph_msg}'}
        if r.status_code == 401:
            return {'success': False, 'error': 'Token rejected — secret may be invalid or expired.'}

        try:
            err = r.json()
            return {'success': False, 'error': f'Graph error {r.status_code}: {err.get("error", {}).get("message", r.text[:300])}'}
        except ValueError:
            return {'success': False, 'error': f'HTTP {r.status_code}: {r.text[:300]}'}

    # Fields we ask Graph for on every message — keeps the page payload
    # small and predictable. Note: $select is NOT supported on /delta
    # for messages, so we apply select only on the initial backfill.
    MESSAGE_FIELDS = (
        'id,subject,from,toRecipients,ccRecipients,bccRecipients,'
        'receivedDateTime,bodyPreview,body,hasAttachments,isRead,'
        'importance,conversationId,internetMessageId'
    )

    def _parse_recipients(self, recipients):
        if not recipients:
            return []
        out = []
        for r in recipients:
            addr = (r.get('emailAddress') or {}).get('address')
            if addr:
                out.append(addr)
        return out

    def _normalize_message(self, m):
        from datetime import datetime as _dt
        sender = (m.get('from') or {}).get('emailAddress') or {}
        received_iso = m.get('receivedDateTime')
        received_dt = None
        if received_iso:
            try:
                received_dt = _dt.fromisoformat(received_iso.replace('Z', '+00:00'))
                received_dt = received_dt.replace(tzinfo=None)  # store naive UTC
            except (ValueError, TypeError):
                pass
        body = m.get('body') or {}
        return {
            'remote_id':           m.get('id'),
            'internet_message_id': m.get('internetMessageId'),
            'conversation_id':     m.get('conversationId'),
            'from_address':        sender.get('address'),
            'from_name':           sender.get('name'),
            'to_addresses':        self._parse_recipients(m.get('toRecipients')),
            'cc_addresses':        self._parse_recipients(m.get('ccRecipients')),
            'bcc_addresses':       self._parse_recipients(m.get('bccRecipients')),
            'subject':             (m.get('subject') or '')[:990],
            'body_text':           body.get('content') if (body.get('contentType') == 'text') else None,
            'body_html':           body.get('content') if (body.get('contentType') == 'html') else None,
            'body_preview':        (m.get('bodyPreview') or '')[:495],
            'received_at':         received_dt,
            'importance':          m.get('importance'),
            'has_attachments':     bool(m.get('hasAttachments')),
            'is_read':             bool(m.get('isRead')),
        }

    def fetch_new_messages(self, limit=500):
        """Pull new messages since last sync using Graph delta queries.

        Strategy:
          - First run ever: walk /mailFolders/inbox/messages/delta from
            the start, paginate via @odata.nextLink, yield messages.
            Save the final @odata.deltaLink as our cursor.
          - Subsequent runs: GET the saved deltaLink — Graph returns
            only messages added/changed since.
          - If Graph returns 410 (deltaLink expired, happens after ~30
            days of inactivity), reset and full-resync.

        Caps at `limit` per call so a stuck queue can't run forever.
        """
        if not self._mailbox():
            return {'success': False, 'error': 'No mailbox configured', 'messages': []}

        token_resp = self._get_access_token()
        if 'error' in token_resp:
            return {'success': False, 'error': token_resp['error'], 'messages': []}
        headers = {
            'Authorization': f'Bearer {token_resp["access_token"]}',
            'Prefer': 'odata.maxpagesize=50',
        }

        delta_token = self.provider.last_delta_token
        if delta_token:
            url = delta_token
        else:
            url = (f'{GRAPH_BASE_URL}/users/{self._mailbox()}'
                   f'/mailFolders/inbox/messages/delta?$select={self.MESSAGE_FIELDS}')

        messages = []
        next_link = url
        new_delta = None
        pages = 0
        max_pages = max(1, (limit + 49) // 50)

        while next_link and pages < max_pages and len(messages) < limit:
            try:
                r = requests.get(next_link, headers=headers, timeout=30)
            except requests.exceptions.RequestException as e:
                return {'success': False, 'error': f'Network: {e}', 'messages': messages}

            if r.status_code == 410:
                # Delta token expired — reset and let next run start over.
                self.provider.last_delta_token = None
                return {'success': False, 'error': 'Delta token expired (410). Resetting cursor; next sync will backfill.', 'messages': []}
            if r.status_code != 200:
                try:
                    err = r.json().get('error', {})
                    msg = err.get('message', r.text[:300])
                except ValueError:
                    msg = f'HTTP {r.status_code}: {r.text[:300]}'
                return {'success': False, 'error': msg, 'messages': messages}

            page = r.json() or {}
            for m in page.get('value') or []:
                # Deletions appear as {'@removed': {...}, 'id': '...'} —
                # we ignore for now (portal-side archive is enough; we
                # keep historical mail even if user deletes upstream).
                if '@removed' in m:
                    continue
                normalized = self._normalize_message(m)
                if normalized.get('remote_id'):
                    messages.append(normalized)

            # Graph returns nextLink while paging through the current snapshot,
            # then deltaLink at the end of the snapshot.
            next_link = page.get('@odata.nextLink')
            new_delta = page.get('@odata.deltaLink') or new_delta
            pages += 1

        return {
            'success':       True,
            'messages':      messages,
            'new_delta':     new_delta,
            'has_more':      bool(next_link),  # true if we hit the limit cap mid-snapshot
            'next_link':     next_link,
        }

    def download_attachment(self, message_remote_id, attachment_remote_id):
        """Fetch a single attachment's binary content (base64).

        Called lazily on first download click — sync time only stores
        attachment metadata, not bytes.
        """
        if not self._mailbox():
            return {'success': False, 'error': 'No mailbox configured'}
        token_resp = self._get_access_token()
        if 'error' in token_resp:
            return {'success': False, 'error': token_resp['error']}

        headers = {'Authorization': f'Bearer {token_resp["access_token"]}'}
        url = (f'{GRAPH_BASE_URL}/users/{self._mailbox()}'
               f'/messages/{message_remote_id}/attachments/{attachment_remote_id}')
        try:
            r = requests.get(url, headers=headers, timeout=60)
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': f'Network: {e}'}

        if r.status_code != 200:
            try:
                err = r.json().get('error', {})
                return {'success': False, 'error': err.get('message', r.text[:300])}
            except ValueError:
                return {'success': False, 'error': f'HTTP {r.status_code}'}

        a = r.json() or {}
        return {
            'success':      True,
            'filename':     a.get('name'),
            'content_type': a.get('contentType'),
            'size':         a.get('size'),
            'content_b64':  a.get('contentBytes'),  # already base64
            'is_inline':    bool(a.get('isInline')),
            'content_id':   a.get('contentId'),
        }

    def list_attachments(self, message_remote_id):
        """Pull metadata for every attachment on a message — no binaries."""
        if not self._mailbox():
            return {'success': False, 'error': 'No mailbox configured', 'attachments': []}
        token_resp = self._get_access_token()
        if 'error' in token_resp:
            return {'success': False, 'error': token_resp['error'], 'attachments': []}

        headers = {'Authorization': f'Bearer {token_resp["access_token"]}'}
        # NB: $select can't include `contentId` on the base attachment
        # type (it only exists on the fileAttachment subtype). The
        # field still comes back in the default response when present;
        # it's just not selectable. We grab everything and pick what
        # we care about.
        url = (f'{GRAPH_BASE_URL}/users/{self._mailbox()}'
               f'/messages/{message_remote_id}/attachments'
               f'?$select=id,name,contentType,size,isInline')
        try:
            r = requests.get(url, headers=headers, timeout=30)
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': f'Network: {e}', 'attachments': []}

        if r.status_code != 200:
            return {'success': False, 'error': f'HTTP {r.status_code}: {r.text[:200]}', 'attachments': []}

        items = []
        for a in (r.json() or {}).get('value') or []:
            items.append({
                'remote_id':    a.get('id'),
                'filename':     a.get('name'),
                'content_type': a.get('contentType'),
                'size':         a.get('size'),
                'is_inline':    bool(a.get('isInline')),
                'content_id':   a.get('contentId'),
            })
        return {'success': True, 'attachments': items}
