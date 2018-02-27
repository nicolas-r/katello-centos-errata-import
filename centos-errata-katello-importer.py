#!/usr/bin/env python3

import sys
import os
import pprint
import csv
import logging
import redis
import json
import subprocess

from yaml import load
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/modules')
from rhnerrata.rhnerrata import rhnErrata
from katello.katello import Katello

# Define some variables
all_erratas = []
all_repositories = {}

if __name__ == '__main__':
    nb_errata = 0

    # Configure PP object
    pp = pprint.PrettyPrinter(indent=2)

    # Create the logger object
    logger = logging.getLogger()
    # Set logger level to DEBUG
    logger.setLevel(logging.DEBUG)

    # Create a formatter object
    formatter = logging.Formatter('%(asctime)s :: %(levelname)s :: %(message)s')

    # Console handler
    steam_handler = logging.StreamHandler()
    steam_handler.setFormatter(formatter)
    steam_handler.setLevel(logging.DEBUG)
    logger.addHandler(steam_handler)

    # Read configuration file
    with open("config.yaml", 'r') as yaml_file:
        conf_data = load(yaml_file, Loader=Loader)
        yaml_file.close()

    ###########################################
    # 1. Read errata's information from Redis #
    ###########################################

    redis_client = redis.StrictRedis(host=conf_data['redis']['server'], port=conf_data['redis']['port'], db=0)
    for errata_id in redis_client.scan_iter(match='CE*'):
        local_errata = rhnErrata(errata_id.decode('utf-8'))
        errata_redis_data = json.loads(redis_client.get(errata_id).decode('utf-8'))
        local_errata.bulk_create(errata_redis_data)
        all_erratas.append(local_errata)
        nb_errata += 1
    logger.info('Number of errata loaded from Redis %d' % nb_errata)

    #############################################################
    # 2. Get data for repositories listed in configuration file #
    #############################################################

    logger.info('Check that all specified repositories in config file really exist in Katello...')
    # Create the Katello object
    katello = Katello({'conf_file': 'config.yaml'})

    # First, get all repositories present in Katello and filter them
    # to keep only the ones defined in the configuration file
    katello_repositories = katello.get_repositories()
    for conf_repo in conf_data['repositories']:
        repo_found = False
        for kat_repo in katello_repositories['results']:
            if conf_repo == kat_repo['label']:
                repo_found = True
                break
        if repo_found is False:
            print("%s doesn't exits in Katello/Satellite" % conf_repo)
            sys.exit(1)

    logger.info('Get repositories information from Katello/Satellite and configuration file...')
    # Get repositories information from Katello/Satellite and configuration file
    for repo in katello_repositories['results']:
        if repo['label'] not in conf_data['repositories']:
            print("skipped")
            continue
        if conf_data['repositories'][repo['label']]['os_release'] not in all_repositories:
            all_repositories[conf_data['repositories'][repo['label']]['os_release']] = {}
        all_repositories[conf_data['repositories'][repo['label']]['os_release']][repo['label']] = {}
        all_repositories[conf_data['repositories'][repo['label']]['os_release']][repo['label']]['id'] = repo['id']
        all_repositories[conf_data['repositories'][repo['label']]['os_release']][repo['label']]['checksumType'] = katello.get_repository_details(repo['id'])['checksum_type']
        all_repositories[conf_data['repositories'][repo['label']]['os_release']][repo['label']]['pulp'] = conf_data['repositories'][repo['label']]['pulp_id']
    # pp.pprint(katello_repositories['results'])

    #############################################################
    # 3. Get errata packages data for the selected repositories #
    #############################################################

    logger.info('Get errata packages data for the selected repositories...')
    for repo_release in all_repositories:
        for repo in all_repositories[repo_release]:
            all_repositories[repo_release][repo]['packages'] = {}
            all_repositories[repo_release][repo]['packages_set'] = []
            all_repositories[repo_release][repo]['nb_erratas'] = 0
            all_repositories[repo_release][repo]['erratas'] = []

            # Get all erratas
            erratas = katello.get_all_erratas(all_repositories[repo_release][repo]['id'])
            for errata in erratas['results']:
                all_repositories[repo_release][repo]['erratas'].append(errata['errata_id'])

            # Get all packages
            rpms = katello.get_all_packages(all_repositories[repo_release][repo]['id'])
            for rpm in rpms['results']:
                all_repositories[repo_release][repo]['packages'][rpm['filename']] = {
                    'version': rpm['version'],
                    'release': rpm['release'],
                    'epoch': rpm['epoch'],
                    'arch': rpm['arch'],
                    'checksum': rpm['checksum'],
                    'name': rpm['name'],
                    'filename': rpm['filename'],
                    'nvra': rpm['nvra'],
                    'nvrea': rpm['nvrea'],
                }
                all_repositories[repo_release][repo]['packages_set'].append(rpm['filename'])
    # pp.pprint(all_repositories)

    #########################
    # 4. Create the  errata #
    #########################

    # Loop over all errata to create them in Katello
    # For each repository, we are checking if the errata's packages matching the os release
    # are present in the repository

    for errata in all_erratas:
        logger.debug("Processing errata %s" % errata.errata_id)

        pkg_found = False
        errata_packages_details = {'packages': []}
        # Loop over all os release
        for repository_release in all_repositories:
            logger.debug("Working on OS release %d" % repository_release)
            # Get errata's packages matching the os release of the current repository
            errata_packages = errata.get_packages_for_os_release(repository_release)
            logger.debug("Packages list for errata %s for OS release %d: %s" % (errata.errata_id, repository_release, errata_packages))
            if errata_packages is not None:
                # Loop over all repositories for a given os release
                for repository_label in all_repositories[repository_release]:
                    logger.debug("Working on repository %s" % repository_label)

                    if errata.errata_id in all_repositories[repository_release][repository_label]['erratas']:
                        logger.debug("Skipping errata %s (already present)" % errata.errata_id)
                        break

                    for errataPkg in errata_packages:
                        if errataPkg in all_repositories[repository_release][repository_label]['packages_set']:
                            pkg_found = True
                            # print('%s found in %s' % (errataPkg, repository_label))
                            errata_packages_details['packages'].append(all_repositories[repository_release][repository_label]['packages'][errataPkg])
                    if pkg_found is True:
                        errata_packages_details['repository_label'] = repository_label
                        all_repositories[repository_release][repository_label]['nb_erratas'] += 1
                        break
                if pkg_found is True:
                    errata_packages_details['repository_release'] = repository_release
                    break
        if pkg_found is True:
            # logger.info('%s will be created' % (errata.id))
            # Create the CSV files for package list
            packages_file = "/tmp/" + errata.errata_id + ".packages.csv"
            if sys.version_info >= (3, 0, 0):
                file = open(packages_file, "w", newline='')
            else:
                file = open(packages_file, 'wb')
            try:
                writer = csv.writer(file)
                for p in errata_packages_details['packages']:
                    writer.writerow([p['name'], p['version'], p['release'], p['epoch'], p['arch'], p['filename'], p['checksum'], all_repositories[errata_packages_details['repository_release']][errata_packages_details['repository_label']]['checksumType'], 'N/A'])
            finally:
                file.close()
            # Create the CSV files for references list
            references_file = "/tmp/" + errata.errata_id + ".references.csv"
            if sys.version_info >= (3, 0, 0):
                file = open(references_file, "w", newline='')
            else:
                file = open(references_file, 'wb')
            try:
                writer = csv.writer(file)
                for ref in errata.get_references():
                    writer.writerow([ref, errata.get_errata_type(), errata.errata_id, errata.get_synopsis()])
            finally:
                file.close()

            pulp_cmd = []
            pulp_cmd.append('pulp-admin')
            pulp_cmd.append('rpm')
            pulp_cmd.append('repo')
            pulp_cmd.append('uploads')
            pulp_cmd.append('erratum')
            pulp_cmd.append('--title=' + errata.get_synopsis())
            pulp_cmd.append('--description=' + errata.get_description())
            pulp_cmd.append('--version=' + str(errata.get_release()))
            pulp_cmd.append('--release=el' + str(errata_packages_details['repository_release']))
            pulp_cmd.append('--type=' + errata.get_errata_type())
            pulp_cmd.append('--severity=' + errata.get_severity())
            pulp_cmd.append('--status=final')
            pulp_cmd.append('--updated=' + errata.get_issue_date())
            pulp_cmd.append('--issued=' + errata.get_issue_date())
            pulp_cmd.append('--reference-csv=' + references_file)
            pulp_cmd.append('--pkglist-csv=' + packages_file)
            pulp_cmd.append('--from=' + errata.get_email())
            pulp_cmd.append('--repo-id=' + all_repositories[errata_packages_details['repository_release']][errata_packages_details['repository_label']]['pulp'])
            pulp_cmd.append('--erratum-id=' + errata.get_errata_id())

            # print(pulp_cmd)
            subprocess.call(pulp_cmd)

            # Clean temporary files
            clean_files = [packages_file, references_file]
            for f in clean_files:
                if os.path.exists(f):
                    os.remove(f)

    for repo_release in all_repositories:
        for repo in all_repositories[repo_release]:
            print("%s %s" % (repo, all_repositories[repo_release][repo]['nb_erratas']))
    sys.exit(0)
