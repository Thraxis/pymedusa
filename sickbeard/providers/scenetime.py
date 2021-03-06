# coding=utf-8
# Author: Idan Gutman
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

from __future__ import unicode_literals

import re
import traceback

from requests.compat import urljoin
from requests.utils import dict_from_cookiejar

from sickbeard import logger, tvcache
from sickbeard.bs4_parser import BS4Parser

from sickrage.helper.common import convert_size, try_int
from sickrage.providers.torrent.TorrentProvider import TorrentProvider


class SceneTimeProvider(TorrentProvider):  # pylint: disable=too-many-instance-attributes
    """SceneTime Torrent provider"""
    def __init__(self):

        # Provider Init
        TorrentProvider.__init__(self, 'SceneTime')

        # Credentials
        self.username = None
        self.password = None

        # URLs
        self.url = 'https://www.scenetime.com'
        self.urls = {
            'login': urljoin(self.url, 'takelogin.php'),
            'search': urljoin(self.url, 'browse.php'),
            'download': urljoin(self.url, 'download.php/{0}/{1}'),
        }

        # Proper Strings

        # Miscellaneous Options

        # Torrent Stats
        self.minseed = None
        self.minleech = None

        # Cache
        self.cache = tvcache.TVCache(self, min_time=20)  # only poll SceneTime every 20 minutes max

    def search(self, search_strings, age=0, ep_obj=None):  # pylint: disable=too-many-locals, too-many-branches
        """
        SceneTime search and parsing

        :param search_string: A dict with mode (key) and the search value (value)
        :param age: Not used
        :param ep_obj: Not used
        :returns: A list of search results (structure)
        """
        results = []
        if not self.login():
            return results

        # Search Params
        search_params = {
            'c2': 1,  # TV/XviD
            'c43': 1,  # TV/Packs
            'c9': 1,  # TV-HD
            'c63': 1,  # TV/Classic
            'c77': 1,  # TV/SD
            'c79': 1,  # Sports
            'c100': 1,  # TV/Non-English
            'c83': 1,  # TV/Web-Rip
            'search': '',
        }

        for mode in search_strings:
            items = []
            logger.log('Search mode: {0}'.format(mode), logger.DEBUG)

            for search_string in search_strings[mode]:

                if mode != 'RSS':
                    logger.log('Search string: {search}'.format
                               (search=search_string), logger.DEBUG)
                    search_params['search'] = search_string

                response = self.get_url(self.urls['search'], params=search_params, returns='response')
                if not response or not response.text:
                    logger.log('No data returned from provider', logger.DEBUG)
                    continue

                with BS4Parser(response.text, 'html5lib') as html:
                    torrent_table = html.find('div', id='torrenttable')
                    torrent_rows = []
                    if torrent_table:
                        torrent_rows = torrent_table.select('tr')

                    # Continue only if at least one release is found
                    if len(torrent_rows) < 2:
                        logger.log('Data returned from provider does not contain any torrents', logger.DEBUG)
                        continue

                    # Scenetime apparently uses different number of cells in #torrenttable based
                    # on who you are. This works around that by extracting labels from the first
                    # <tr> and using their index to find the correct download/seeders/leechers td.
                    labels = [label.get_text(strip=True) for label in torrent_rows[0]('td')]

                    # Skip column headers
                    for result in torrent_rows[1:]:
                        cells = result('td')
                        if len(cells) < len(labels):
                            continue

                        try:
                            link = cells[labels.index('Name')].find('a')
                            torrent_id = link['href'].replace('details.php?id=', '').split('&')[0]
                            title = link.get_text(strip=True)
                            download_url = self.urls['download'].format(torrent_id, '{0}.torrent'.format(title.replace(' ', '.')))
                            if not all([title, download_url]):
                                continue

                            seeders = try_int(cells[labels.index('Seeders')].get_text(strip=True))
                            leechers = try_int(cells[labels.index('Leechers')].get_text(strip=True))

                            # Filter unseeded torrent
                            if seeders < min(self.minseed, 1):
                                if mode != 'RSS':
                                    logger.log("Discarding torrent because it doesn't meet the "
                                               "minimum seeders: {0}. Seeders: {1}".format
                                               (title, seeders), logger.DEBUG)
                                continue

                            torrent_size = cells[labels.index('Size')].get_text()
                            size = convert_size(torrent_size) or -1

                            item = {
                                'title': title,
                                'link': download_url,
                                'size': size,
                                'seeders': seeders,
                                'leechers': leechers,
                                'pubdate': None,
                                'hash': None,
                            }
                            if mode != 'RSS':
                                logger.log('Found result: {0} with {1} seeders and {2} leechers'.format
                                           (title, seeders, leechers), logger.DEBUG)

                            items.append(item)
                        except (AttributeError, TypeError, KeyError, ValueError, IndexError):
                            logger.log('Failed parsing provider. Traceback: {0!r}'.format
                                       (traceback.format_exc()), logger.ERROR)
                            continue

            results += items

        return results

    def login(self):
        if any(dict_from_cookiejar(self.session.cookies).values()):
            return True

        login_params = {
            'username': self.username,
            'password': self.password,
        }

        response = self.get_url(self.urls['login'], post_data=login_params, returns='text')
        if not response:
            logger.log('Unable to connect to provider', logger.WARNING)
            return False

        if re.search('Username or password incorrect', response):
            logger.log('Invalid username or password. Check your settings', logger.WARNING)
            return False

        return True


provider = SceneTimeProvider()
