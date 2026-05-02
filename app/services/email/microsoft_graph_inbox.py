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
    # small and predictable.
    MESSAGE_FIELDS = (
        'id,subject,from,toRecipients,ccRecipients,bccRecipients,'
        'receivedDateTime,bodyPreview,body,hasAttachments,isRead,'
        'importance,conversationId,internetMessageId,parentFolderId'
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

    def _normalize_message(self, m, folder_name_map=None):
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
        parent_folder_id = m.get('parentFolderId')
        folder_name = None
        if parent_folder_id and folder_name_map:
            folder_name = folder_name_map.get(parent_folder_id)
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
            'parent_folder_id':    parent_folder_id,
            'folder_name':         folder_name,
        }

    def _load_folder_name_map(self, headers):
        """Build {folder_id: display_name} for every folder in the mailbox.

        Walks top-level folders + their direct children. Two levels covers
        Inbox/Sent Items/Drafts/Archive/custom folders plus user-created
        sub-folders inside them. Anything deeper falls back to id-only
        (folder_name=None on the message), which is fine — the inbox UI
        groups by id and just shows the leaf id when it can't resolve a
        name.

        Best-effort: any failure (network, 404, empty response) returns
        whatever we built so far, so a folder lookup hiccup doesn't
        break the whole sync.
        """
        name_map = {}

        def fetch(url):
            try:
                r = requests.get(url, headers=headers, timeout=15)
            except requests.exceptions.RequestException:
                return []
            if r.status_code != 200:
                return []
            return (r.json() or {}).get('value') or []

        base = f'{GRAPH_BASE_URL}/users/{self._mailbox()}/mailFolders'
        top_url = f'{base}?$top=100&$select=id,displayName,childFolderCount'
        for top in fetch(top_url):
            fid = top.get('id')
            fname = top.get('displayName') or ''
            if not fid:
                continue
            name_map[fid] = fname
            if (top.get('childFolderCount') or 0) > 0:
                child_url = f'{base}/{fid}/childFolders?$top=100&$select=id,displayName'
                for child in fetch(child_url):
                    cid = child.get('id')
                    cname = child.get('displayName') or ''
                    if cid:
                        name_map[cid] = f'{fname} / {cname}' if fname else cname

        return name_map

    def fetch_new_messages(self, limit=500):
        """Pull new messages since last sync using Graph delta queries.

        Graph's /messages/delta is folder-scoped — there is no
        account-wide variant ("Change tracking is not supported against
        microsoft.graph.message"). So we iterate every folder we
        discover and keep a separate delta cursor per folder, all
        serialized into provider.last_delta_token as a JSON dict
        keyed by folder id.

        Strategy per folder:
          - First sync of a folder: walk
            /mailFolders/{id}/messages/delta from the start, paginate
            via @odata.nextLink, save the final @odata.deltaLink.
          - Subsequent syncs: GET the saved deltaLink — Graph returns
            only messages added/changed since.
          - 410 on a folder's deltaLink: drop that folder's cursor;
            next sync re-backfills it from scratch.

        We resolve folder display names once per call from /mailFolders
        and tag each message with `parent_folder_id` + `folder_name`.

        Caps at `limit` total messages per call (across all folders) so
        a stuck queue can't run forever; sets has_more=True if any
        folder had unfetched pages when we hit the cap.
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

        # Resolve folder display names + discover the folder ids to sync.
        folder_name_map = self._load_folder_name_map(headers)
        if not folder_name_map:
            return {'success': False, 'error': 'No folders discovered for mailbox.', 'messages': []}

        # Per-folder delta cursors — serialized as JSON in last_delta_token.
        # If the column was last written by an older revision (single URL
        # string for the inbox), ignore it and start fresh; the resync
        # cost is bounded by `limit`.
        import json as _json
        raw = self.provider.last_delta_token
        try:
            delta_tokens = _json.loads(raw) if raw else {}
            if not isinstance(delta_tokens, dict):
                delta_tokens = {}
        except (ValueError, TypeError):
            delta_tokens = {}

        messages = []
        new_tokens = dict(delta_tokens)
        has_more = False

        for folder_id, folder_label in folder_name_map.items():
            if len(messages) >= limit:
                has_more = True
                break

            cursor = delta_tokens.get(folder_id)
            if cursor:
                next_link = cursor
            else:
                next_link = (f'{GRAPH_BASE_URL}/users/{self._mailbox()}'
                             f'/mailFolders/{folder_id}/messages/delta'
                             f'?$select={self.MESSAGE_FIELDS}')

            folder_delta = None
            folder_pages = 0
            # Per-folder page cap — 50 pages * 50 msgs/page = 2500 ceiling
            # for any single folder's first backfill. The outer `limit`
            # check stops us earlier in practice.
            max_folder_pages = 50

            while next_link and folder_pages < max_folder_pages and len(messages) < limit:
                try:
                    r = requests.get(next_link, headers=headers, timeout=30)
                except requests.exceptions.RequestException as e:
                    logger.warning(f'Folder {folder_label!r} fetch network error: {e}')
                    break

                if r.status_code == 410:
                    # Folder's delta token expired — drop cursor and let
                    # the next sync rebackfill this folder from scratch.
                    new_tokens.pop(folder_id, None)
                    logger.info(f'Folder {folder_label!r} delta expired; will rebackfill next sync.')
                    break
                if r.status_code != 200:
                    try:
                        err_msg = r.json().get('error', {}).get('message', r.text[:200])
                    except ValueError:
                        err_msg = f'HTTP {r.status_code}'
                    logger.warning(f'Folder {folder_label!r} fetch failed: {err_msg}')
                    break

                page = r.json() or {}
                for m in page.get('value') or []:
                    # Deletions appear as {'@removed': {...}, 'id': '...'} —
                    # we ignore for now (portal-side archive is enough; we
                    # keep historical mail even if user deletes upstream).
                    if '@removed' in m:
                        continue
                    normalized = self._normalize_message(m, folder_name_map)
                    if normalized.get('remote_id'):
                        messages.append(normalized)
                        if len(messages) >= limit:
                            break

                # Graph returns nextLink while paging through the current snapshot,
                # then deltaLink at the end of the snapshot.
                next_link = page.get('@odata.nextLink')
                folder_delta = page.get('@odata.deltaLink') or folder_delta
                folder_pages += 1

            if next_link:
                # We stopped mid-snapshot (limit hit or page cap) — keep
                # the old cursor so the next sync resumes correctly. If
                # there was no old cursor, leave new_tokens as-is too;
                # next sync will start the folder over from the top.
                has_more = True
            elif folder_delta:
                new_tokens[folder_id] = folder_delta

        # Serialize back to JSON for storage. None if everything's empty.
        new_delta_serialized = _json.dumps(new_tokens) if new_tokens else None

        return {
            'success':       True,
            'messages':      messages,
            'new_delta':     new_delta_serialized,
            'has_more':      has_more,
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
