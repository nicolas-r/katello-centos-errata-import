#!/usr/bin/env python3

import sys

from yaml import load
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

try:
    import simplejson as json
except ImportError:
    import json

try:
    import requests
except ImportError:
    print("Please install the python-requests module.")
    sys.exit(-1)
from requests.packages.urllib3.exceptions import InsecureRequestWarning


class Katello(object):
    """docstring for Katello"""

    def __init__(self, params):
        # Read configuration file
        if params['conf_file'] is not None:
            with open(params['conf_file'], 'r') as yaml_file:
                conf_data = load(yaml_file, Loader=Loader)
                yaml_file.close()

        self.katello_server_url = conf_data['katello']['server']
        self.katello_api_url = conf_data['katello']['api_url']
        self.katello_api = self.katello_server_url + self.katello_api_url
        self.katello_user = conf_data['katello']['username']
        self.katello_password = conf_data['katello']['password']
        self.ssl_verify = conf_data['katello']['ssl_verify']
        self.post_headers = {'Content-Type': 'application/json'}

    def _get_json(self, location, data):
        """
        Performs a GET using the passed URL location
        """
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
        if data is None:
            data = {
                'per_page': 99999,
            }
        else:
            data['per_page'] = 99999

        r = requests.get(
            self.katello_api + location,
            data=data,
            auth=(self.katello_user, self.katello_password),
            verify=self.ssl_verify,
        )
        return r.json()

    def _post_json(self, location, data):
        """
        Performs a POST and passes the data to the URL location
        """
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
        if data is not None:
            _data = json.dump(data)
        else:
            _data = None
        result = requests.post(
            self.katello_api + location,
            data=_data,
            auth=(self.katello_user, self.katello_password),
            verify=self.ssl_verify,
            headers=self.post_headers)
        return result.json()

    def get_repositories(self):
        return(self._get_json('repositories', None))

    def get_repository_details(self, repository_id):
        return(self._get_json('repositories/' + str(repository_id), None))

    def get_repository_erratas(self, repository_id):
        data = {
            'repository_id': repository_id,
        }
        return(self._get_json('errata', data))

    def get_repository_packages(self, repository_id):
        data = {
            'repository_id': repository_id,
        }
        # return(self._get_json('repositories/' + str(repository_id) + '/packages', None))
        return(self._get_json('packages', data))

    def start_repo_sync(self, repository_id):
        return(self._post_json('repositories/' + str(repository_id) + '/sync', None))


if __name__ == '__main__':
    print("Katello API class for python")
