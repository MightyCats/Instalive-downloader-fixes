from datetime import datetime
import json

from . import helpers
from . import globals
from .constants import Constants

def get_csrf_token():
    response = globals.session.session.get(Constants.LOGIN_PAGE)
    return helpers.get_shared_data(response.text).get("csrf_token", None)

def do_login():
    now_epoch = int(datetime.now().timestamp())
    login_data = {
    "username": globals.session.username,
    "enc_password": f"#PWD_INSTAGRAM_BROWSER:0:{now_epoch}:{globals.session.password}",
    "queryParams": {},
    "optIntoOneTap": "false"
    }
    response = globals.session.session.post(Constants.LOGIN_AJAX, data=login_data, timeout=5)
    return json.loads(response.text)

def get_login_state():
    response = globals.session.session.get(Constants.BASE_WEB, timeout=5)
    return helpers.get_shared_data(response.text)

def _normalize_user(user, username=None):
    if not isinstance(user, dict):
        return None
    user_id = user.get("pk") or user.get("id") or user.get("user_id")
    if not user_id:
        return None
    if username:
        u = user.get("username")
        if not u or u.lower() != username.lower():
            return None
    user = dict(user)
    user["id"] = str(user_id)
    user["pk"] = user_id
    return user


def _find_user_in_payload(value, username):
    """Find a user object in current/legacy Instagram response envelopes."""
    if isinstance(value, dict):
        candidate = _normalize_user(value, username)
        if candidate:
            return candidate
        for key, child in value.items():
            found = _find_user_in_payload(child, username)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_user_in_payload(child, username)
            if found:
                return found
    return None


def _request(method, url, **kwargs):
    try:
        return getattr(globals.session.session, method)(url, timeout=8, **kwargs)
    except Exception:
        return None


def _parse_json(response):
    if response is None:
        return None
    try:
        return response.json()
    except Exception:
        return None


def _mobile_request_headers():
    """Build headers that match Instagram's mobile app API rather than the web browser."""
    import hashlib
    import uuid

    headers = dict(getattr(Constants, "MOBILE_HEADERS", {}) or {})
    username = str(getattr(globals.session, "username", "pyinstalive"))
    device_seed = hashlib.md5(username.encode("utf-8")).hexdigest()
    headers["X-IG-Android-ID"] = "android-" + device_seed[:16]
    headers["X-IG-Device-ID"] = str(uuid.uuid5(uuid.NAMESPACE_DNS, "pyinstalive-device:" + username))
    headers["X-IG-App-Locale"] = "en_US"
    headers["X-IG-Device-Locale"] = "en_US"
    headers["X-IG-Mapped-Locale"] = "en_US"
    headers["X-IG-Timezone-Offset"] = "0"

    try:
        cookies = globals.session.session.cookies.get_dict()
        ds_user_id = cookies.get("ds_user_id")
        if ds_user_id:
            headers["IG-U-DS-USER-ID"] = str(ds_user_id)
            headers["IG-INTENDED-USER-ID"] = str(ds_user_id)
    except Exception:
        pass
    return headers


def _web_request_headers():
    headers = dict(getattr(Constants, "BASE_HEADERS", {}) or {})
    headers.setdefault("Referer", Constants.BASE_WEB)
    headers.setdefault("Accept", "*/*")
    return headers


def _get_user_info_from_search(username):
    """Resolve an exact username using the mobile users/search endpoint."""
    import time
    params = {
        "timezone_offset": "0",
        "q": username,
        "count": 30,
    }
    response = _request(
        "get",
        Constants.USER_SEARCH,
        params=params,
        headers=_mobile_request_headers(),
    )
    if response is None:
        return {}
    data = _parse_json(response)
    if not isinstance(data, dict) or data.get("status") == "fail":
        return {}
    users = data.get("users", [])
    if not isinstance(users, list):
        return {}
    wanted = username.casefold()
    for user in users:
        if not isinstance(user, dict):
            continue
        candidate_name = user.get("username")
        if isinstance(candidate_name, str) and candidate_name.casefold() == wanted:
            normalized = _normalize_user(user)
            if normalized:
                print(f"[D] user_search: exact username matched, id={normalized.get('id')}") if DEBUG_USER_LOOKUP else None
                return {"data": {"user": normalized}}
    return {}


def _get_user_info_from_usernameinfo(username):
    """Resolve a username using Instagram's mobile usernameinfo endpoint."""
    response = _request(
        "get",
        Constants.USERNAME_INFO.format(username),
        headers=_mobile_request_headers(),
    )
    if response is None or response.status_code != 200:
        return {}
    data = _parse_json(response)
    if data is None:
        return {}
    user = _find_user_in_payload(data, username)
    if user:
        return {"data": {"user": user}}
    return {}


def _get_user_info_from_username_feed(username):
    """Resolve a username through the web feed/user/username endpoint."""
    response = _request(
        "get",
        Constants.USER_FEED_BY_USERNAME.format(username),
        params={"count": 1},
        headers=_web_request_headers(),
    )
    if response is None or response.status_code != 200:
        return {}
    data = _parse_json(response)
    if data is None:
        return {}
    user = _find_user_in_payload(data, username)
    if user:
        return {"data": {"user": user}}
    return {}


def _get_user_info_from_username_stream(username):
    """Resolve a username using Instagram's mobile profile stream resolver."""
    response = _request(
        "get",
        Constants.USERNAME_INFO_STREAM.format(username),
        headers=_mobile_request_headers(),
    )
    if response is None or response.status_code != 200:
        return {}
    data = _parse_json(response)
    if data is None:
        return {}
    user = _find_user_in_payload(data, username)
    if user:
        return {"data": {"user": user}}
    return {}


def _get_user_info_from_profile_page(username):
    """Resolve user ID from the authenticated Instagram profile HTML."""
    import re
    url = Constants.BASE_WEB + username.strip('/') + "/"
    headers = _web_request_headers()
    headers.update({
        "X-Requested-With": "XMLHttpRequest",
        "X-Asbd-Id": "359341",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Dest": "document",
    })
    response = _request("get", url, headers=headers)
    if response is None or response.status_code != 200:
        return {}
    text = response.text or ""
    # Instagram has used several serialized representations over time.
    patterns = [
        r'"profilePage_(\d+)"',
        r'"user_id"\s*:\s*"?(\d+)"?',
        r'"pk"\s*:\s*"?(\d+)"?[^{}]{0,500}?"username"\s*:\s*"' + re.escape(username) + r'"',
        r'"id"\s*:\s*"?(\d+)"?[^{}]{0,500}?"username"\s*:\s*"' + re.escape(username) + r'"',
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            user_id = m.group(1)
            return {"data": {"user": {"id": str(user_id), "pk": int(user_id), "username": username}}}
    return {}

def get_user_info():
    username = globals.download.download_user

    for resolver in (
        _get_user_info_from_username_feed,
        _get_user_info_from_profile_page,
        _get_user_info_from_search,
        _get_user_info_from_usernameinfo,
        _get_user_info_from_username_stream,
    ):
        info = resolver(username)
        if info:
            return info
    return {}

def get_reels_tray():
    response = globals.session.session.get(Constants.REELS_TRAY, timeout=5)
    return json.loads(response.text)

def get_single_live():
    """Fetch initial live metadata using the same web_info endpoint as the
    reference Instagram-live-stream-recorder project.

    Fail closed on denied, malformed, or incomplete responses so a single
    recording attempt does not cascade into further requests with bad IDs.
    """
    import logging

    user_id = str(globals.download.download_user_id or "").strip()
    if not user_id:
        return {"status": "fail", "message": "Missing target user ID"}

    # Instagram-live-stream-recorder uses i.instagram.com/api/v1/live/web_info
    # with a session cookie, csrf token and the browser app id.
    url = "https://i.instagram.com/api/v1/live/web_info/?target_user_id={}".format(user_id)
    session = globals.session.session
    try:
        cookies = session.cookies.get_dict()
    except Exception:
        cookies = {}
    csrf = cookies.get("csrftoken") or ""
    headers = dict(getattr(Constants, "BASE_HEADERS", {}) or {})
    headers.update({
        "Accept": "*/*",
        "Referer": Constants.BASE_WEB,
        "X-CSRFToken": csrf,
        "X-IG-App-ID": "936619743392459",
        "X-IG-WWW-Claim": "0",
    })
    if cookies:
        headers["Cookie"] = "; ".join("{}={}".format(k, v) for k, v in cookies.items())

    try:
        response = session.get(url, headers=headers, timeout=8)
    except Exception as exc:
        return {"status": "fail", "message": "Live info request failed: {}".format(exc)}

    if response.status_code in (401, 403, 429):
        body = (getattr(response, "text", "") or "").replace("\\r", " ").replace("\\n", " ").strip()
        body = body[:240]
        suffix = ": {}".format(body) if body else ""
        return {"status": "fail", "message": "Instagram denied live-info request (HTTP {}){}".format(response.status_code, suffix)}
    if response.status_code != 200:
        # Short response excerpt helps distinguish session and endpoint errors.
        # Do not log request cookies or authorization headers.
        body = (getattr(response, "text", "") or "").replace("\\r", " ").replace("\\n", " ").strip()
        body = body[:240]
        suffix = ": {}".format(body) if body else ""
        return {"status": "fail", "message": "Live-info request returned HTTP {}{}".format(response.status_code, suffix)}
    try:
        payload = response.json()
    except Exception:
        return {"status": "fail", "message": "Live-info response was not valid JSON"}
    if not isinstance(payload, dict):
        return {"status": "fail", "message": "Live-info response had an unexpected format"}

    # Keep Instagram's numeric broadcast id in "id".  "media_id" /
    # "live_post_id" can be a different media identifier (sometimes a
    # composite "<media_id>_<owner_id>"). PyInstaLive's comment and heartbeat
    # endpoints require the numeric broadcast id, not that media identifier.
    broadcast_id = payload.get("id") or payload.get("strong_id__") or payload.get("str_id")
    media_id = payload.get("media_id") or payload.get("live_post_id") or broadcast_id
    mpd_url = payload.get("dash_abr_playback_url")
    if not broadcast_id or not isinstance(mpd_url, str) or not mpd_url.strip():
        message = payload.get("message") or payload.get("status") or "Live stream metadata is missing"
        return {"status": "fail", "message": str(message)}

    normalized = dict(payload)
    normalized["id"] = str(broadcast_id)
    if media_id is not None:
        normalized["media_id"] = str(media_id)
    normalized.setdefault("broadcast_status", "active")
    # The web_info payload may not contain broadcast_owner; keep a safe dict so
    # older PyInstaLive code cannot call .get() on None.
    owner = normalized.get("broadcast_owner")
    if not isinstance(owner, dict):
        normalized["broadcast_owner"] = {"username": globals.download.download_user}
    if not isinstance(normalized.get("cobroadcasters"), list):
        normalized["cobroadcasters"] = []
    return normalized

def _response_json_or_error(response, label):
    """Parse JSON safely and preserve response details for diagnosis."""
    try:
        payload = response.json()
    except Exception:
        try:
            body = (response.text or "").strip().replace("\r", " ").replace("\n", " ")[:240]
        except Exception:
            body = ""
        return {"status": "fail", "message": "{} returned non-JSON response (HTTP {}): {}".format(label, getattr(response, "status_code", "?"), body or "<empty body>")}
    if not isinstance(payload, dict):
        return {"status": "fail", "message": "{} returned unexpected JSON type {}".format(label, type(payload).__name__)}
    if getattr(response, "status_code", 200) >= 400:
        return {"status": "fail", "message": "{} returned HTTP {}: {}".format(label, response.status_code, str(payload)[:240])}
    return payload


def get_comments():
    """Fetch LIVE comments through Instagram's same-origin web endpoint.

    The mobile endpoint currently returns challenge_required/unsupported_version
    for some otherwise usable web sessions. The Instagram web live page uses
    /api/v1/live/{broadcast_id}/get_comment/ with the browser session cookies.
    """
    try:
        broadcast_id = globals.download.livestream_object_init.get('id')
        if not broadcast_id:
            return {"status": "fail", "message": "Live comments request skipped: broadcast ID is missing"}

        session = globals.session.session
        try:
            cookies = session.cookies.get_dict()
        except Exception:
            cookies = {}
        headers = _web_request_headers()
        username = str(getattr(globals.download, "download_user", "") or "").strip().lstrip("@")
        referer = Constants.BASE_WEB + (username + "/" if username else "")
        headers.update({
            "Referer": referer,
            "Origin": Constants.BASE_WEB.rstrip("/"),
            "X-Requested-With": "XMLHttpRequest",
            "X-ASBD-ID": "359341",
            "X-IG-App-ID": "936619743392459",
            "X-CSRFToken": cookies.get("csrftoken", ""),
            "Accept": "application/json, text/plain, */*",
        })
        url = Constants.BASE_API + "live/{}/get_comment/".format(str(broadcast_id))
        # Keep the cursor used by the original PyInstaLive API and explicitly
        # request a normal batch of comments, as expected by Instagram's API.
        params = {
            "last_comment_ts": str(globals.comments.comments_last_ts),
            "comment_count": "150",
            "encoding_tag": "instagram_live_comments",
        }
        response = session.get(url, params=params, headers=headers, timeout=8)
        result = _response_json_or_error(response, "Live comments request")
        if isinstance(result, dict) and result.get("status") == "fail":
            # Include the selected endpoint in the log message so an API-side
            # rejection can be distinguished from a later JSON-save problem.
            result["message"] = "{} [endpoint=web, broadcast_id={}]".format(
                result.get("message", "request failed"), str(broadcast_id)
            )
        elif isinstance(result, dict):
            comment_items = result.get("comments")
            if not isinstance(comment_items, list):
                return {"status": "fail", "message": "Live comments response has no comments list [endpoint=web, broadcast_id={}]".format(str(broadcast_id))}
        return result
    except Exception as exc:
        return {"status": "fail", "message": "Live comments request failed: {}".format(exc)}


def get_stream_data():
    try:
        response = globals.session.session.get(Constants.LIVE_STATE_USER.format(globals.download.download_user_id), timeout=5)
        return _response_json_or_error(response, "Live stream-state request")
    except Exception as exc:
        return {"status": "fail", "message": "Live stream-state request failed: {}".format(exc)}


def do_heartbeat():
    try:
        response = globals.session.session.post(Constants.LIVE_HEARTBEAT.format(globals.download.livestream_object_init.get('id')), timeout=5)
        return _response_json_or_error(response, "Live heartbeat request")
    except Exception as exc:
        return {"status": "fail", "message": "Live heartbeat request failed: {}".format(exc)}
