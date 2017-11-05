#!/usr/bin/env python3

import re


class rhnErrata(object):

    """docstring for Errata"""
    def __init__(self, errata_id):
        self.id = errata_id
        self.release = None
        self.severity = None
        self.description = None
        self.synopsis = None
        self.issue_date = None
        self.type = None
        self.email = None
        self.os_releases = []
        self.all_packages = []
        self.references = []
        self.packages_by_os_release = {}

    def bulk_create(self, data):
        self.release = data['release']
        self.severity = data['severity']
        self.description = data['description']
        self.synopsis = data['synopsis']
        self.issue_date = data['issue_date']
        self.type = data['type']
        self.email = data['email']
        self.os_releases = data['os_releases']
        self.all_packages = data['all_packages']
        self.references = data['references']
        self.packages_by_os_release = data['packages_by_os_release']

    def get_id(self):
        return self.id

    def set_release(self, errata_release):
        self.release = errata_release

    def get_release(self):
        return self.release

    def set_severity(self, errata_severity):
        self.severity = errata_severity

    def get_severity(self):
        return self.severity

    def set_description(self, errata_description):
        self.description = errata_description

    def get_description(self):
        return self.description

    def set_synopsis(self, errata_synopsis):
        self.synopsis = errata_synopsis

    def get_synopsis(self):
        return self.synopsis

    def set_issue_date(self, errata_issue_date):
        self.issue_date = errata_issue_date

    def get_issue_date(self):
        return self.issue_date

    def set_type(self, errata_type):
        self.type = errata_type

    def get_type(self):
        return self.type

    def set_email(self, errata_email):
        self.email = errata_email

    def get_email(self):
        return self.email

    def add_os_release(self, os_release):
        self.os_releases.append(os_release)
        self.packages_by_os_release[os_release] = {}
        self.packages_by_os_release[os_release]['packages'] = []

    def get_os_releases(self):
        return self.os_releases

    def add_reference(self, errata_reference):
        self.references.append(errata_reference)

    def get_references(self):
        return self.references

    def add_package(self, errata_package):
        self.all_packages.append(errata_package)
        for os_release in self.os_releases:
            if not re.match(r'.+\.src\.rpm', errata_package):
                if re.match(r'.+\.(el|EL|rhel|RHEL)' + str(os_release) + r'.+', errata_package):
                    self.packages_by_os_release[os_release]['packages'].append(errata_package)

    def get_packages_for_os_release(self, os_release):
        if os_release in self.os_releases:
            # pkgs = []
            # for package in self.all_packages:
            #     # Skip src package
            #     if re.match(r'.+\.src\.rpm', package):
            #         continue
            #     if re.match(r'.+\.(el|EL|rhel|RHEL)' + str(os_release) + r'.+', package):
            #         pkgs.append(package)
            # return pkgs
            return self.packages_by_os_release[str(os_release)]['packages']
        else:
            return None


if __name__ == '__main__':
    print("Errata classes for python")
