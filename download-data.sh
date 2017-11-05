#!/bin/bash

CURDIR=$(pwd)

cd ${CURDIR}/data
wget -N http://cefs.steve-meier.de/errata.latest.xml
wget -N https://www.redhat.com/security/data/oval/com.redhat.rhsa-all.xml
cd ${CURDIR}
