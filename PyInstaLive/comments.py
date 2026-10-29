import time
import codecs
import json
import os

from . import logger
from . import globals
from . import api
from .download import Download

class Comments:
    def __init__(self):
        self.comments = []
        self.comments_last_ts = 0
        # Stop repeated requests when Instagram explicitly requires a security challenge.
        self.challenge_blocked = False
        self.challenge_warning_shown = False

    def retrieve_comments(self):
        if self.challenge_blocked:
            return
        if self.comments_last_ts == 0:
            self.comments_last_ts = int(globals.download.timestamp)
        current_comments = self.comments
        before_count = len(self.comments)
        comments_response = api.get_comments()
        if not isinstance(comments_response, dict) or comments_response.get("status") == "fail":
            if isinstance(comments_response, dict):
                message = str(comments_response.get("message", "invalid response"))
                lowered = message.lower()
                if "challenge_required" in lowered or "checkpoint_required" in lowered:
                    self.challenge_blocked = True
                    if not self.challenge_warning_shown:
                        logger.warn("Instagram requires a security challenge for comments. Comment polling has been paused to avoid repeated requests; video recording will continue. Check the account through Instagram's official app/site.")
                        self.challenge_warning_shown = True
                    return
                logger.warn("Comment API response unavailable: {}".format(message))
            else:
                logger.warn("Comment API returned an invalid response; continuing without new comments.")
            return
        new_comments = comments_response.get("comments", [])
        if not isinstance(new_comments, list):
            logger.warn("Comment API returned an unexpected comments field; continuing without new comments.")
            return
        for i, comment in enumerate(new_comments):
            elapsed = int(time.time()) - int(globals.download.timestamp)
            new_comments[i].update({"total_elapsed": elapsed})
        self.comments_last_ts = (new_comments[0]['created_at_utc'] if new_comments else self.comments_last_ts)
        current_comments.extend(new_comments)
        after_count = len(current_comments)
        if after_count > before_count:
            globals.download.livestream_object['comments'] = current_comments
        self.comments = current_comments

    def generate_log(self):
        try:
            if globals.args.generate_comments_path:
                if os.path.isfile(globals.args.generate_comments_path):
                    self.comments = json.load(open(globals.args.generate_comments_path, "r", encoding="utf-8")).get("comments", [])
                    globals.download = Download()
                    globals.download.data_generate_comments_path = globals.args.generate_comments_path.replace(".json", ".log")

                else:
                    logger.error("Could not save comments: The JSON file does not exist.")
                    return
            if self.comments:
                logger.info("Saving {} comment{} to text file.".format(len(self.comments), "s" if len(self.comments) > 1 else ""))
            else:
                logger.binfo("There are no available comments to save.")
                return
            comments_timeline = {}
            for c in self.comments:
                if 'offset' in c:
                    for k in list(c.get('comment')):
                        c[k] = c.get('comment', {}).get(k)
                    c['created_at_utc'] = c.get('offset')
                created_at_utc = str(2 * (c.get('created_at_utc') // 2))
                comment_list = comments_timeline.get(created_at_utc) or []
                comment_list.append(c)
                comments_timeline[created_at_utc] = comment_list

            if comments_timeline:
                comment_errors = 0
                total_comments = 0
                timestamps = sorted(list(comments_timeline))
                comments = []
                for tc in timestamps:
                    t = comments_timeline[tc]

                    comments_log = ''
                    for c in t:
                        try:
                            comments_log += '{}{}\n\n'.format(time.strftime('%H:%M:%S\n', time.gmtime(c.get("total_elapsed"))), '{}: {}'.format(c.get('user', {}).get('username'),c.get('text')))
                        except Exception:
                            comment_errors += 1
                            try:
                                comments_log += '{}{}\n\n'.format(time.strftime('%H:%M:%S\n', time.gmtime(c.get("total_elapsed"))), '{}: {}'.format(c.get('user', {}).get('username'),c.get('text').encode('ascii', 'ignore')))
                            except Exception:
                                pass
                        total_comments += 1
                    comments.append(comments_log)

                with codecs.open(globals.download.data_generate_comments_path, 'w', 'utf-8-sig') as log_outfile:
                    log_outfile.write(''.join(comments))
                logger.info("Successfully saved text file: {}".format(os.path.basename(globals.download.data_generate_comments_path)))
        except Exception as e:
            logger.error("Could not save comments: {:s}".format(str(e)))