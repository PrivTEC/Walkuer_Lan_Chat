# Walkuer LAN Chat - Local API (v1)

Base URL
- `http://127.0.0.1:<port>/api/v1/`
- The port is the same as the local file server. You can see it in Settings (API URL).

Access
- Localhost only (127.0.0.1).
- Token required for all POST endpoints and most GET endpoints.
- Send token via header `X-API-Token: <token>` or query `?token=<token>`.
- Token is shown in Settings (API Token).

Content Type
- JSON: `application/json; charset=utf-8`

Common Response
```json
{"ok": true}
```
Error:
```json
{"ok": false, "error": "message"}
```

Limits
- Text limit: 8 KB UTF-8.
- History limit for API: max 200 per request.
- File send expects a local file path on this machine.

Endpoints

1) Self description (no auth)
GET `/api/v1/`
Response:
```json
{
  "name": "Walkuer LAN Chat API",
  "version": "v1",
  "base_url": "http://127.0.0.1:51338/api/v1",
  "auth": {"required": true, "header": "X-API-Token", "query": "token"},
  "endpoints": []
}
```

2) Human/AI help (no auth)
GET `/api/v1/help`
Response: plain text.

3) Status
GET `/api/v1/status`
Response:
```json
{
  "ok": true,
  "api_enabled": true,
  "api_base_url": "http://127.0.0.1:51338/api/v1",
  "queue_size": 0,
  "self": {
    "sender_id": "uuid",
    "name": "User",
    "avatar_sha256": ""
  }
}
```

4) Peers
GET `/api/v1/peers`
Response:
```json
{"ok": true, "peers": [{"sender_id": "...", "name": "..."}]}
```

5) Messages
GET `/api/v1/messages?limit=50`
Response:
```json
{"ok": true, "messages": [/* history items */]}
```

6) Current pin
GET `/api/v1/pin`
Response:
```json
{"ok": true, "pinned": {"target_id": "...", "preview": "...", "name": "..."}}
```

7) Send text
POST `/api/v1/send`
Body:
```json
{
  "text": "hello",
  "message_id": "optional-uuid",
  "reply_to": "optional-message-id",
  "reply_name": "optional",
  "reply_preview": "optional",
  "reply_type": "optional"
}
```
Response:
```json
{"ok": true, "message_id": "uuid"}
```

8) Send file
POST `/api/v1/send/file`
Body:
```json
{"path": "C:\\\\path\\\\to\\\\file.txt"}
```
Response:
```json
{"ok": true, "queued": true}
```

9) Edit message
POST `/api/v1/edit`
Body:
```json
{"message_id": "uuid", "text": "new text"}
```
Response:
```json
{"ok": true}
```

10) Undo message (delete)
POST `/api/v1/undo`
Body:
```json
{"message_id": "uuid"}
```
Response:
```json
{"ok": true}
```

11) Pin message
POST `/api/v1/pin`
Body:
```json
{"message_id": "uuid", "preview": "optional"}
```
Response:
```json
{"ok": true}
```

12) Unpin message
POST `/api/v1/unpin`
Body:
```json
{"message_id": "uuid"}
```
Response:
```json
{"ok": true}
```

Examples

Send text:
```
curl -X POST "http://127.0.0.1:51338/api/v1/send" ^
  -H "X-API-Token: <token>" ^
  -H "Content-Type: application/json" ^
  -d "{\"text\":\"Hello LAN\"}"
```

Get peers:
```
curl "http://127.0.0.1:51338/api/v1/peers?token=<token>"
```
