# coding=utf-8
# Author: Marvin Pinto <me@marvinp.ca>
# Author: Dennis Lutter <lad1337@gmail.com>
# Author: Aaron Bieber <deftly@gmail.com>
# URL: http://code.google.com/p/sickbeard/
#
# This file is part of Medusa.
#
# Medusa is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Medusa is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Medusa. If not, see <http://www.gnu.org/licenses/>.

import time

from requests.compat import urlencode
from six.moves.urllib.error import HTTPError
from six.moves.http_client import HTTPSConnection

import sickbeard
from sickbeard import logger
from sickbeard.common import notifyStrings, NOTIFY_SNATCH, NOTIFY_SNATCH_PROPER, NOTIFY_DOWNLOAD, NOTIFY_SUBTITLE_DOWNLOAD, NOTIFY_GIT_UPDATE, NOTIFY_GIT_UPDATE_TEXT, NOTIFY_LOGIN_TEXT, NOTIFY_LOGIN
from sickrage.helper.exceptions import ex

API_URL = "https://api.pushover.net/1/messages.json"


class Notifier(object):
    def __init__(self):
        pass

    def test_notify(self, userKey=None, apiKey=None):
        return self._notifyPushover("This is a test notification from Medusa", 'Test', userKey=userKey, apiKey=apiKey, force=True)

    def _sendPushover(self, msg, title, sound=None, userKey=None, apiKey=None):
        """
        Sends a pushover notification to the address provided

        msg: The message to send (unicode)
        title: The title of the message
        sound: The notification sound to use
        userKey: The pushover user id to send the message to (or to subscribe with)
        apiKey: The pushover api key to use
        returns: True if the message succeeded, False otherwise
        """

        if userKey is None:
            userKey = sickbeard.PUSHOVER_USERKEY

        if apiKey is None:
            apiKey = sickbeard.PUSHOVER_APIKEY

        if sound is None:
            sound = sickbeard.PUSHOVER_SOUND

        logger.log(u"Pushover API KEY in use: " + apiKey, logger.DEBUG)

        # build up the URL and parameters
        msg = msg.strip()

        # send the request to pushover
        try:
            if sickbeard.PUSHOVER_SOUND != "default":
                args = {
                    "token": apiKey,
                    "user": userKey,
                    "title": title.encode('utf-8'),
                    "message": msg.encode('utf-8'),
                    "timestamp": int(time.time()),
                    "retry": 60,
                    "expire": 3600,
                    "sound": sound,
                }
            else:
                # sound is default, so don't send it
                args = {
                    "token": apiKey,
                    "user": userKey,
                    "title": title.encode('utf-8'),
                    "message": msg.encode('utf-8'),
                    "timestamp": int(time.time()),
                    "retry": 60,
                    "expire": 3600,
                }

            if sickbeard.PUSHOVER_DEVICE:
                args["device"] = sickbeard.PUSHOVER_DEVICE

            conn = HTTPSConnection("api.pushover.net:443")
            conn.request("POST", "/1/messages.json",
                         urlencode(args), {"Content-type": "application/x-www-form-urlencoded"})

        except HTTPError as e:
            # if we get an error back that doesn't have an error code then who knows what's really happening
            if not hasattr(e, 'code'):
                logger.log(u"Pushover notification failed." + ex(e), logger.ERROR)
                return False
            else:
                logger.log(u"Pushover notification failed. Error code: " + str(e.code), logger.ERROR)

            # HTTP status 404 if the provided email address isn't a Pushover user.
            if e.code == 404:
                logger.log(u"Username is wrong/not a pushover email. Pushover will send an email to it", logger.WARNING)
                return False

            # For HTTP status code 401's, it is because you are passing in either an invalid token, or the user has not added your service.
            elif e.code == 401:

                # HTTP status 401 if the user doesn't have the service added
                subscribeNote = self._sendPushover(msg, title, sound=sound, userKey=userKey, apiKey=apiKey)
                if subscribeNote:
                    logger.log(u"Subscription sent", logger.DEBUG)
                    return True
                else:
                    logger.log(u"Subscription could not be sent", logger.ERROR)
                    return False

            # If you receive an HTTP status code of 400, it is because you failed to send the proper parameters
            elif e.code == 400:
                logger.log(u"Wrong data sent to pushover", logger.ERROR)
                return False

            # If you receive a HTTP status code of 429, it is because the message limit has been reached (free limit is 7,500)
            elif e.code == 429:
                logger.log(u"Pushover API message limit reached - try a different API key", logger.ERROR)
                return False

        logger.log(u"Pushover notification successful.", logger.INFO)
        return True

    def notify_snatch(self, ep_name, is_proper):
        title=notifyStrings[(NOTIFY_SNATCH, NOTIFY_SNATCH_PROPER)[is_proper]]
        if sickbeard.PUSHOVER_NOTIFY_ONSNATCH:
            self._notifyPushover(title, ep_name)

    def notify_download(self, ep_name, title=notifyStrings[NOTIFY_DOWNLOAD]):
        if sickbeard.PUSHOVER_NOTIFY_ONDOWNLOAD:
            self._notifyPushover(title, ep_name)

    def notify_subtitle_download(self, ep_name, lang, title=notifyStrings[NOTIFY_SUBTITLE_DOWNLOAD]):
        if sickbeard.PUSHOVER_NOTIFY_ONSUBTITLEDOWNLOAD:
            self._notifyPushover(title, ep_name + ": " + lang)

    def notify_git_update(self, new_version="??"):
        if sickbeard.USE_PUSHOVER:
            update_text = notifyStrings[NOTIFY_GIT_UPDATE_TEXT]
            title = notifyStrings[NOTIFY_GIT_UPDATE]
            self._notifyPushover(title, update_text + new_version)

    def notify_login(self, ipaddress=""):
        if sickbeard.USE_PUSHOVER:
            update_text = notifyStrings[NOTIFY_LOGIN_TEXT]
            title = notifyStrings[NOTIFY_LOGIN]
            self._notifyPushover(title, update_text.format(ipaddress))

    def _notifyPushover(self, title, message, sound=None, userKey=None, apiKey=None, force=False):
        """
        Sends a pushover notification based on the provided info or Medusa config

        title: The title of the notification to send
        message: The message string to send
        sound: The notification sound to use
        userKey: The userKey to send the notification to
        apiKey: The apiKey to use to send the notification
        force: Enforce sending, for instance for testing
        """

        if not sickbeard.USE_PUSHOVER and not force:
            logger.log(u"Notification for Pushover not enabled, skipping this notification", logger.DEBUG)
            return False

        logger.log(u"Sending notification for " + message, logger.DEBUG)

        return self._sendPushover(message, title, sound=sound, userKey=userKey, apiKey=apiKey)
