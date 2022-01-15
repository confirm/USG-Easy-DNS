#!/usr/bin/env python

from __future__ import unicode_literals, print_function

import argparse
import cookielib
import hashlib
import logging
import json
import os
import re
import ssl
import urllib
import urllib2

#: Name of the default site when nothing else is specified.
DEFAULT_SITE = 'default'

#: The default username for the UniFi controller.
DEFAULT_USERNAME = 'usg'

#: The default password for the UniFi controller.
DEFAULT_PASSWORD = 'usg'

#: The default hosts file.
DEFAULT_FILE = '/config/user-data/hosts'

#: Flag if the SSL verification should be skipped.
SKIP_SSL_VERIFICATION = False


LOGGER = logging.getLogger(__name__)


class UniFiController:
    '''
    Class to talk to the UniFi controller.
    '''

    def __init__(self, url, skip_ssl_verification=SKIP_SSL_VERIFICATION):
        '''
        Constructor.

        :param str url: The base URL
        '''
        self.url = url

        if skip_ssl_verification:
            ssl._create_default_https_context = ssl._create_unverified_context

        cookie_jar  = cookielib.CookieJar()
        self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookie_jar))

    def _request(self, endpoint, data=None):
        '''
        Send a request to an UniFi API endpoint.

        :param str endpoint: The endpoint
        :param dict data: The data

        :return: The response
        :rtype: dict
        '''
        url  = os.path.join(self.url, 'api', endpoint)
        data = json.dumps(data) if data else None

        LOGGER.debug('Sending request to %s with data %s', url, data)
        response = self.opener.open(fullurl=url, data=data)

        return json.load(response)

    def login(self, username, password):
        '''
        Login into the UniFi controller and get the cookie.

        :param str username: The UniFi username
        :param str password: The UniFi password
        '''
        LOGGER.info('Logging in')

        response = self._request(
            endpoint='login',
            data={
                'username': username,
                'password': password,
            }
        )

    def get_clients(self, site=DEFAULT_SITE):
        '''
        Get the clients.

        :return: The clients
        :type: dict
        '''
        LOGGER.info('Getting clients')

        return self._request(endpoint='s/{}/stat/sta'.format(site))['data']

    def get_fixed_ips(self, site=DEFAULT_SITE):
        '''
        Get the fixed client IP addresses in a dict, where the dict key is the
        client name and the value is its IP address.

        :param str site: The site name
        :param bool only_aliases: Flag if only clients with aliases should be returned

        :return: A list of IP address & hostname tuples
        :rtype: list
        '''
        clients = []

        for client in self.get_clients():
            if 'fixed_ip' not in client:
                continue

            ip   = client['fixed_ip']
            name = client['name'] if 'name' in client else client['hostname']
            name = re.sub(pattern=r'[\s_-]+', repl='-', string=name, flags=re.IGNORECASE)
            name = re.sub(pattern='[^0-9a-z-]', repl='', string=name, flags=re.IGNORECASE)

            LOGGER.debug('Adding host %s with IP address %s', name, ip)
            clients.append((ip, name))

        clients.sort(key=lambda item: item[0])

        return clients


class DnsHosts:
    '''
    Class to generate the hosts file and inform the DNS server about updates.
    '''

    def __init__(self, file):
        '''
        Constructor.

        :param str file: The file path
        '''
        self.file = file

    @classmethod
    def calculate_checksum(self, clients):
        '''
        Calculate the checksum of the clients.
        '''
        checksum = hashlib.md5(str(clients)).hexdigest()
        LOGGER.debug('Calculated checksum of new clients is %s', checksum)
        return checksum

    @property
    def checksum(self):
        '''
        The checksum of the current file.

        :return: None or the checksum
        :rtype: None or str
        '''
        try:
            with file(self.file, 'r') as fh:
                checksum = fh.readline()[2:].strip()
        except IOError:
            return checksum

        LOGGER.debug('Checksum of existing file is %s', checksum)
        return checksum

    def update(self, clients):
        '''
        Update the hosts file and notify the DNS server.
        '''
        self.update_file(clients=clients)

    def update_file(self, clients):
        '''
        Check the hosts file and update it if anything changed.

        :param list clients: The new client list

        :return: State if the file was updated
        :rtype: bool
        '''
        old_checksum = self.checksum
        new_checksum = self.calculate_checksum(clients)

        if old_checksum == new_checksum:
            LOGGER.info('No changes found, file is up to date')
            return False

        LOGGER.info('Changes found, updating file')
        with open(args.file, 'w') as file:
            file.write('# {}\n'.format(new_checksum))
            for host, ip in clients:
                file.write('{:15s} {}\n'.format(ip, host))

        return True


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='USG Easy DNS')

    parser.add_argument('-u', '--username', default=DEFAULT_USERNAME, help='UniFi username')
    parser.add_argument('-p', '--password', default=DEFAULT_PASSWORD, help='UniFi password')
    parser.add_argument('-f', '--file', default=DEFAULT_FILE, help='the hosts file')
    parser.add_argument('-i', '--insecure', action='store_true', help='skip SSL verification')
    parser.add_argument('-d', '--debug', action='store_true', help='activate debug mode')
    parser.add_argument('url', help='the URL of the UniFi controller')

    args = parser.parse_args()

    logging.basicConfig(format='%(message)s', level='DEBUG' if args.debug else 'INFO')

    controller = UniFiController(url=args.url, skip_ssl_verification=args.insecure)
    controller.login(username=args.username, password=args.password)

    dns_hosts = DnsHosts(file=args.file)
    dns_hosts.update(clients=controller.get_fixed_ips())
