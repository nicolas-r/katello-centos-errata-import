# katello-centos-errata-import
This script imports CentOS Errata into Katello and use preformatted information from http://cefs.steve-meier.de/

This is a python rewrite of a perl script made by [brdude](https://github.com/brdude/pulp_centos_errata_import) with some modifications, like the use of a redis cache.

To run this script on CentOS you need:
 - pulp-admin-client
 - pulp-rpm-admin-extensions
 - redis server
 - Some python modules
   - lxml
   - PyYAML
   - pyaml
   - redis
   - requests

It has been tested on CentOS 7 with the default python version and with python34 from EPEL. I'm using [pew](https://github.com/berdario/pew) to test it inside a python virtual environment

# Warning

- I offer no guarantees that this script will work for you. It is offered as is!
- I'm not an experimented Python programer, so this script may look horrific to anyone familiar with the language.

# Prerequisites

## Authentication
pulp-admin must authenticate to pulp. This authentication information can be provided to pulp-admin in two ways.

  1. User certificate (~/.pulp/user-cert.pem)  
     If you are using this script with katello, the foreman-installer creates a certificate suitable for use with pulp. You can use the cert by doing the following:

```shell
mkdir ~/.pulp/
chmod 0700 ~/.pulp/
sudo cat /etc/pki/katello/certs/pulp-client.crt /etc/pki/katello/private/pulp-client.key > ~/.pulp/user-cert.pem
chmod 400 ~/.pulp/user-cert.pem
```

  2. Admin configuration file (~/.pulp/admin.conf)  
     You can provide the auth credentials in the pulp-admin configuration file. Simply create ~/.pulp/admin.conf, you can get the password from /etc/pulp/server.conf (default_password).

```shell
mkdir ~/.pulp/
chmod 0700 ~/.pulp/
sudo cp /etc/pulp/admin/admin.conf ~/.pulp/
sed -i "20,30s/^# host:.*/host: $(hostname -f)/g" ~/.pulp/admin.conf
PULP_PASS=$(sudo awk '/^default_password/ {print $2}' /etc/pulp/server.conf)
cat >> ~/.pulp/admin.conf << EOF

[auth]
username: admin
password: ${PULP_PASS}
EOF
chmod 0400 ~/.pulp/admin.conf
```

It is probably advisable to not store these credentials in a normal user's home directory. You might consider using the root user for pulp-admin tasks. Then non-privileged users can be given rights explicitly through sudo. If you choose this way, the previous commands are still valid but as you will be connected as root, using sudo will be useless.

## Redis server
Modify the configuration file to change the bind address if needed, and to enable persistent storage.

Right now, these scripts are not using authentification to connect to the redis server, so protected mode must be disabled (depending of your redis version).

## Configuration file
- Rename the sample-config.yaml to config.yaml
- Fill the information for
  - your Katello server
  - the directory that will contains the data files
  - your redis server

For the reposotiries part, this is a little tricky.
- katello-repository-label: this is the 'Label' fied that you can find in the webui, by clicking on a repository name inside a product
- pulp_id: this is the 'Backend Identifier' fied that you can find in the webui, by clicking on a repository name inside a product
- release: this is the CentOS release matching the repository content (must be 6 or 7 right now)

# Usage
  1. Sync repositories
  2. Run the script download-data.sh to download the last datafiles from Steve Meier and Red Hat sites
  3. Run the script centos-errata-redis-loader.py to store errata data into Redis
  4. Run the script centos-errata-katello-importer.py to start the creation of the errata into Katello
  5. Sync repositories again so that errata is published. (The errata will not show up on the Katello/Foreman interface until this step is completed.)

# Contributing

Please feel free to make pull requests for any
issues or errors in the script you may find.


