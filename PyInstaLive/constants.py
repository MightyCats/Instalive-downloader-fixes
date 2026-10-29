import sys


class Constants:
    SCRIPT_VERSION = "4.0.3-beta"
    PYTHON_VERSION = sys.version.split(" ")[0]
    CONFIG_TEMPLATE = """
[pyinstalive]
username = johndoe
password = grapefruits
session_file = None
cookies_file = None
download_path = {:s}
download_comments = True
clear_temp_files = True
cmd_on_started =
cmd_on_ended =
ffmpeg_path = 
log_to_file = True
no_assemble = False
use_locks = True
send_heartbeat = True
proxy =
    """



    BASE_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'x-ig-app-id': '936619743392459',
        'x-asbd-id': '359341',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Sec-Ch-Ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
    }
    MOBILE_HEADERS = {
        'User-Agent': 'Instagram 237.0.0.14.102 Android (25/7.1.2; 320dpi; 720x1280; samsung; SM-G973N; aosp; android_x86; en_US; 373310563)',
        'X-IG-App-ID': '567067343352427',
        'X-IG-Capabilities': '3brTv10=',
        'X-IG-Connection-Type': 'WIFI',
        'X-FB-HTTP-Engine': 'Liger',
        'Accept-Language': 'en-US',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'close',
    }
    BASE_WEB = "https://www.instagram.com/"
    BASE_API = "https://www.instagram.com/api/v1/"
    BASE_MOBILE_API = "https://i.instagram.com/api/v1/"

    LOGIN_PAGE = BASE_WEB + "accounts/login/"
    LOGIN_AJAX = BASE_WEB + "accounts/login/ajax/"

    REELS_TRAY = BASE_API + "live/reels_tray_broadcasts/"
    # Instagram began returning HTTP 400 for web_profile_info on some
    # professional/business accounts in July 2026.  Resolve the username
    # through the username-feed endpoint instead.
    USER_FEED_BY_USERNAME = BASE_API + "feed/user/{:s}/username/"
    USER_INFO = BASE_API + "users/web_profile_info/?username={:s}"
    LIVE_STATE_USER = BASE_API + "live/web_info/?target_user_id={:s}"
    LIVE_HEARTBEAT = BASE_API + "live/{:s}/heartbeat_and_get_viewer_count/"
    LIVE_COMMENT = BASE_MOBILE_API + "live/{:s}/get_comment/"

    USER_SEARCH = BASE_MOBILE_API + "users/search/"
    USERNAME_INFO_STREAM = BASE_MOBILE_API + "users/{:s}/usernameinfo_stream/"
    USERNAME_INFO = BASE_MOBILE_API + "users/{:s}/usernameinfo/"
