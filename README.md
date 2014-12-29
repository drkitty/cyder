Cyder
===

[![Build Status](https://travis-ci.org/OSU-Net/cyder.png?branch=master)](https://travis-ci.org/OSU-Net/cyder)

Django DNS/DHCP web manager.

Meant as a ground-up rewrite of Oregon State University's DNS/DHCP network web
manager, Maintain, which was previously built with PHP, this would be the fifth
coming of Maintain.

Cyder provides a web frontend built with user experience and visual design in
mind. It provides an easy-to-use and attractive interface for network
administrators to create, view, delete, and update DNS records and DHCP
objects.

On the backend are build scripts that generate DNS BIND files and DHCP builds
directly from the database backing Cyder. The database schema and backend
data models have been designed-to-spec using the RFCs.

![Cyder](http://i.imgur.com/p8Rmbvv.png)


Installation
============

### Dependencies

#### Linux packages

- Fedora:

    ```
sudo yum install python-devel openldap-devel cyrus-sasl-devel openssl-devel python-pip community-mysql
sudo yum install community-mysql-devel community-mysql-server MySQL-python gcc rubygems bind
sudo systemctl start mysqld
    ```

- Debian:

    ```
sudo apt-get install python-dev libldap2-dev libsasl2-dev libssl-dev rubygems
    ```

<!-- TODO: add MySQL, pip, etc. -->

#### Miscellaneous

```
sudo gem install sass
```

### Setup

- Clone the repo:

    ```
git clone 'git@github.com:OSU-Net/cyder.git'
cd cyder
    ```

- Set up virtualenv (recommended):

    ```
virtualenv .env
    ```

    Do `source .env/bin/activate` now and every time you run your shell.

- Install submodules and other dependencies:

    ```
git submodule update --init --recursive
pip install -r requirements/dev.txt
    ```
- Set up settings

    ```
cp cyder/settings/local.py-dist cyder/settings/local.py
sed -i "s|SASS_BIN = '[^']*'|SASS_BIN = '`which sass`'|" cyder/settings/local.py
    ```
    
    Then set the *MIGRATION* settings appropriately. See [the Maintain migration docs](https://github.com/OSU-Net/cyder/wiki/Overview:-Migration) for details.

- Create an empty database for Cyder. (A separate user is recommended.) Enter database settings into `cyder/settings/local.py`.

- Bring database schema up to date:

    ```
./manage.py syncdb
./manage.py migrate cyder
    ```
    
    Creating a superuser is unnecessary—Cyder comes with a test superuser named `test_superuser`.

- Copy data from Maintain's database into *MIGRATION\_DB* and sanitize it, then migrate data from *MIGRATION\_DB* to Cyder:

    ```
./manage.py maintain_migrate -qt
    ```

### Optional setup

- Install a PEP8 linter as a git pre-commit hook:

    ```
pip install git+https://github.com/jbalogh/check.git#egg=check
cp requirements/.pre-commit .git/hooks/pre-commit
    ```

### Coding Standards

Adhere to coding standards, or feel the wrath of my **erupting burning finger**.

- [Mozilla Webdev Coding Guide](http://mozweb.readthedocs.org/en/latest/reference/index.html)
- [JQuery JavaScript Style Guide](http://contribute.jquery.org/style-guide/js/)
- Strict 80-character limit on lines of code in Python, recommended in HTML and JS
- 2-space HTML indents, 4-space indent everything else
- Single-quotes over double-quotes
- Use whitespace to separate logical blocks of code — no 200 line walls of code
- Reduce, reuse, recycle — this project is very generic-heavy, look for previously invented wheels
- Keep files litter-free: throw away old print statements and pdb imports
- Descriptive variable names — verbose > incomprehensible

For multi-line blocks of code, either use 4-space hanging indents or visual indents.

```
# Hanging Indent
Ship.objects.get_or_create(
    captain='Mal', address='Serenity', class='Firefly')

# Visual Indent
Ship.objects.get_or_create(captain='Mal', address='Serenity',
                           class='Firefly')
```
