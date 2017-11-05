#!/usr/bin/env python3

import sys
import os
import hashlib
import pprint
import re
import logging
import json

try:
    from lxml import etree
except ImportError:
    print("Please install the lxml module.")
    sys.exit(-1)

try:
    from yaml import load
except ImportError:
    print("Please install the PyYAML module.")
    sys.exit(-1)
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

try:
    import redis
except ImportError:
    print("Please install the redis module.")
    sys.exit(-1)

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/modules')
from rhnerrata.rhnerrata import rhnErrata


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

    # Data files
    errata_file = conf_data['data_files']['errata_files']
    oval_file = conf_data['data_files']['oval_files']

    # Compute the sha1 of the errata file
    logger.info('Computing SHA1 sum of %s' % errata_file)
    errata_file_hash = hashlib.sha1()
    errata_file_fh = open(errata_file, 'rb')
    errata_file_hash.update(errata_file_fh.read())
    errata_file_fh.close()
    logger.debug('SHA1 sum of %s: %s' % (errata_file, errata_file_hash.hexdigest()))

    redis_client = redis.StrictRedis(host=conf_data['redis']['server'], port=conf_data['redis']['port'], db=0)
    logger.debug('Reading SHA1 sum from Redis')
    if redis_client.get('errata_file_hash') is not None:
        redis_file_errata_hash = redis_client.get('errata_file_hash').decode('utf8')
        logger.debug('Redis SHA1 sum: %s' % redis_file_errata_hash)
    else:
        logger.debug('SHA1 not found in Redis.')
        redis_file_errata_hash = None

    if redis_file_errata_hash == errata_file_hash.hexdigest():
        logger.info('SHA1 sums are the same, nothing to do.')
        sys.exit(0)
    else:
        # Open the files and read them
        logger.info('Reading %s...' % (errata_file))
        errata_xml = etree.parse(errata_file)
        errata_xml_root = errata_xml.getroot()
        logger.info('Done')

        logger.info('Reading %s...' % (oval_file))
        oval_xml = etree.parse(oval_file)
        oval_xml_root = oval_xml.getroot()
        logger.info('Done')

        # Process errata in XML file
        # Go through each errata
        logger.debug('Processing errata file %s...' % (errata_file))
        for errata in errata_xml_root:
            # Only consider CentOS errata
            if not re.match(r'^CE', errata.tag):
                logger.debug('Skpping %s : not CentOS errata' % errata.tag)
                continue

            logger.debug("Retrieving data for errata %s" % (errata.tag))

            # Rename the errata
            errata_id = re.sub(r'--', r':', errata.tag)

            # Skip if the errata is already present in Redis
            if redis_client.get(errata_id) is not None:
                logger.debug('Skpping %s : already present in Redis' % errata_id)
                continue

            # Get errata information
            local_errata = rhnErrata(errata_id)
            local_errata.set_synopsis(errata.attrib['synopsis'].replace(',', ';'))
            local_errata.set_issue_date(errata.attrib['issue_date'])
            local_errata.set_release(errata.attrib['release'])
            local_errata.set_email(errata.attrib['from'])
            if 'severity' in errata.attrib:
                local_errata.set_severity(errata.attrib['severity'])
            else:
                local_errata.set_severity('Low')
            local_errata.set_type(errata.attrib['type'])
            for ref in errata.attrib['references'].split():
                local_errata.add_reference(ref)

            for errata_info in errata:
                if errata_info.tag == 'os_release':
                    local_errata.add_os_release(int(errata_info.text))
                elif errata_info.tag == 'packages':
                    local_errata.add_package(errata_info.text)

            # Generate OVAL ID for security errata
            oval_id = ""
            match_obj = re.match(r'CESA-(\d+):(\d+)', errata_id)
            if match_obj:
                    oval_id = "oval:com.redhat.rhsa:def:%s%04d" % (match_obj.group(1), int(match_obj.group(2)))
                    logger.debug("%s is a security errata, searching for OVALID %s" % (errata_id, oval_id))
                    oval_elem = oval_xml.xpath("//o:definition[@id='" + oval_id + "']/o:metadata/o:description",
                                               namespaces={'o': 'http://oval.mitre.org/XMLSchema/oval-definitions-5'})
                    if oval_elem:
                        logger.debug("OVALID %s found" % (oval_id))
                        local_errata.set_description(oval_elem[0].text)

            if local_errata.description is None:
                local_errata.set_description(local_errata.synopsis)

            redis_client.set(errata_id, json.dumps(local_errata.__dict__))
            nb_errata += 1
        logger.info('Updating hash value in Redis')
        redis_file_errata_hash = redis_client.set('errata_file_hash', errata_file_hash.hexdigest().encode('utf8'))
        logger.info('Number of errata created %d' % nb_errata)
