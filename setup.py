#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" distribute- and pip-enabled setup.py """

try:
    import ConfigParser
except ImportError:
    import configparser as ConfigParser
import logging
import os
import re
import sys

# ----- overrides -----

# set these to anything but None to override the automatic defaults
author = None
author_email = None
dependency_links = None
long_description = None
packages = None
package_name = None
package_data = None
scripts = None
requirements_file = None
requirements = None
version = None
test_suite = None

# ---------------------


# ----- control flags -----

# fallback to setuptools if distribute isn't found
setup_tools_fallback = False

# don't include subdir named 'tests' in package_data
skip_tests = True

# print some extra debugging info
debug = True

# use numpy.distutils instead of setuptools
use_numpy = False

# -------------------------
update_url = "https://raw.githubusercontent.com/braingram/simple_setup/master/setup.py"

# this next line is important for the 'fetch' option (see below)
# MARK
if (len(sys.argv) > 1) and sys.argv[1] == 'fetch':
    _overrides = {}
    _locals = locals()
    for _k in _locals.keys():
        if (_k[0] != '_') and not isinstance(_locals[_k], type(sys)):
            _overrides[_k] = _locals[_k]
    if len(sys.argv) > 2:
        target_fn = sys.argv[2]
    else:
        target_fn = __file__
    print("Fetching a new simple_setup.py to {}".format(target_fn))
    import urllib2
    new_ss = urllib2.urlopen(update_url)
    with open(target_fn, 'w') as target:
        found_mark = False
        for l in new_ss:
            if found_mark or len(l.strip()) == 0:
                target.write(l)
            else:
                if l[0] == '#':
                    if l.strip() == '# MARK':
                        found_mark = True
                    target.write(l)
                    continue
                lt = l.split('=')
                key = lt[0].strip()
                if (len(lt) == 2) and (key in _overrides):
                    # copy over the overrides
                    target.write("{} = {!r}\n".format(key, _overrides[key]))
                else:
                    target.write(l)
                    continue
    print("successfully fetched new setup.py")
    sys.exit(0)

if debug:
    logging.basicConfig(level=logging.DEBUG)
# distribute import and testing
try:
    import distribute_setup
    distribute_setup.use_setuptools()
    logging.debug("distribute_setup.py imported and used")
except ImportError:
    # fallback to setuptools?
    # distribute_setup.py was not in this directory
    if not (setup_tools_fallback):
        import setuptools
        # check if setuptools is distribute
        vt = setuptools.__version__.split('.')
        if len(vt) == 1:
            vmajor = int(vt[0])
            vminor = 0
        elif len(vt) > 1:
            vmajor = int(vt[0])
            vminor = int(vt[1])
        if (hasattr(setuptools, '_distribute') and
                setuptools._distribute) or (vmajor > 0 or vminor > 6):
            logging.debug("distribute_setup.py not found, "
                          "defaulted to system distribute")
        else:
            raise ImportError(
                "distribute was not found and fallback "
                "to setuptools was not allowed")
    else:
        logging.debug("distribute_setup.py not found, "
                      "defaulting to system setuptools")

import setuptools


def find_scripts():
    return [s for s in setuptools.findall('scripts/')
            if os.path.splitext(s)[1] != '.pyc']


def package_to_path(package):
    """
    Convert a package (as found by setuptools.find_packages)
    e.g. "foo.bar" to usable path
    e.g. "foo/bar"

    No idea if this works on windows
    """
    return package.replace('.', '/')


def find_subdirectories(package):
    """
    Get the subdirectories within a package
    This will include resources (non-submodules) and submodules
    """
    try:
        subdirectories = next(os.walk(package_to_path(package)))[1]
    except StopIteration:
        subdirectories = []
    return subdirectories


def subdir_findall(dir, subdir):
    """
    Find all files in a subdirectory and return paths relative to dir

    This is similar to (and uses) setuptools.findall
    However, the paths returned are in the form needed for package_data
    """
    strip_n = len(dir.split('/'))
    path = '/'.join((dir, subdir))
    return ['/'.join(s.split('/')[strip_n:]) for s in setuptools.findall(path)]


def find_package_data(packages):
    """
    For a list of packages, find the package_data

    This function scans the subdirectories of a package and considers all
    non-submodule subdirectories as resources, including them in
    the package_data

    Returns a dictionary suitable for setup(package_data=<result>)
    """
    package_data = {}
    for package in packages:
        package_data[package] = []
        for subdir in find_subdirectories(package):
            if '.'.join((package, subdir)) in packages:  # skip submodules
                logging.debug("skipping submodule %s/%s" % (package, subdir))
                continue
            if subdir == '__pycache__':
                logging.debug("skipping %s/__pycache__" % package)
                continue
            if skip_tests and (subdir == 'tests'):  # skip tests
                logging.debug("skipping tests %s/%s" % (package, subdir))
                continue
            package_data[package] += \
                subdir_findall(package_to_path(package), subdir)
    return package_data


def parse_requirements(file_name):
    """
    from:
        http://cburgmer.posterous.com/pip-requirementstxt-and-setuppy
    """
    requirements = []
    with open(file_name, 'r') as f:
        for line in f:
            if re.match(r'(\s*#)|(\s*$)', line):
                continue
            if re.match(r'\s*-e\s+', line):
                requirements.append(re.sub(r'\s*-e\s+.*#egg=(.*)$',
                                           r'\1', line).strip())
            elif re.match(r'\s*-f\s+', line):
                pass
            else:
                requirements.append(line.strip())
    return requirements


def parse_dependency_links(file_name):
    """
    from:
        http://cburgmer.posterous.com/pip-requirementstxt-and-setuppy
    """
    dependency_links = []
    with open(file_name) as f:
        for line in f:
            if re.match(r'\s*-[ef]\s+', line):
                dependency_links.append(re.sub(r'\s*-[ef]\s+',
                                               '', line))
    return dependency_links


def detect_version():
    """
    Try to detect the main package/module version by looking at:
        module.__version__

    otherwise, return 'dev'
    """
    try:
        m = __import__(package_name, fromlist=['__version__'])
        return getattr(m, '__version__', 'dev')
    except ImportError:
        pass
    return 'dev'


def author_info_from_pypirc():
    """
    Try to read author name and email from ~/.pypirc (section simple).

    In addition to the normal content for pypirc include the following to
    allow this function to read your name and email

    [simple_setup]
    author: Joe
    author_email: joe@schmo.org
    """
    author = None
    author_email = None
    fn = os.path.expanduser('~/.pypirc')
    if os.path.exists(fn):
        c = ConfigParser.SafeConfigParser()
        c.read(fn)
        if c.has_section('simple_setup'):
            if c.has_option('simple_setup', 'author'):
                author = c.get('simple_setup', 'author')
            if c.has_option('simple_setup', 'author_email'):
                author_email = c.get('simple_setup', 'author_email')
    return author, author_email


def long_description_from_readme():
    s = None
    fn = os.path.join(os.path.dirname(__file__), 'README')
    if os.path.exists(fn):
        with open(fn, 'r') as f:
            s = f.read()
    return s


def include_requirements_file_in_manifest(fn):
    mfn = os.path.join(os.path.dirname(__file__), 'MANIFEST.in')
    if os.path.exists(mfn):
        included = False
        with open(mfn, 'r') as f:
            for l in f:
                if fn in l:
                    included = True
        if not included:
            with open(mfn, 'a') as f:
                f.writelines(["include {}".format(fn), ])
    else:
        with open(mfn, 'w') as f:
            f.writelines(["include {}".format(fn), ])


# ----------- Override defaults here ----------------
if packages is None:
    packages = setuptools.find_packages()

if len(packages) == 0:
    raise Exception("No valid packages found")

if package_name is None:
    package_name = packages[0]

if package_data is None:
    package_data = find_package_data(packages)

if scripts is None:
    scripts = find_scripts()

if requirements_file is None:
    requirements_file = 'requirements.txt'

if os.path.exists(requirements_file):
    if requirements is None:
        requirements = parse_requirements(requirements_file)
    if dependency_links is None:
        dependency_links = parse_dependency_links(requirements_file)
    # include requirements_file in MANIFEST.in
    include_requirements_file_in_manifest(requirements_file)
else:
    if requirements is None:
        requirements = []
    if dependency_links is None:
        dependency_links = []

if version is None:
    version = detect_version()

if author is None:
    author, email = author_info_from_pypirc()  # save email for later
else:
    email = None

if author_email is None:
    if email is not None:  # if email was previously gotten
        author_email = email
    else:
        _, author_email = author_info_from_pypirc()

if long_description is None:
    long_description = long_description_from_readme()

if test_suite is None:
    if os.path.exists('%s/tests.py' % package_name):
        test_suite = "%s.tests.suite" % package_name


if debug:
    logging.debug("Module name: %s" % package_name)
    for package in packages:
        logging.debug("Package: %s" % package)
        logging.debug("\tData: %s" % str(package_data[package]))
    logging.debug("Scripts:")
    for script in scripts:
        logging.debug("\tScript: %s" % script)
    logging.debug("Requirements:")
    for req in requirements:
        logging.debug("\t%s" % req)
    logging.debug("Dependency links:")
    for dl in dependency_links:
        logging.debug("\t%s" % dl)
    logging.debug("Version: %s" % version)
    logging.debug("Author: %s" % author)
    logging.debug("Author email: %s" % author_email)
    logging.debug("Test Suite: %s" % test_suite)

if __name__ == '__main__':

    sub_packages = packages

    if use_numpy:
        from numpy.distutils.misc_util import Configuration
        config = Configuration(package_name, '', None)

        for sub_package in sub_packages:
            print('adding', sub_package)
            config.add_subpackage(sub_package)

        from numpy.distutils.core import setup
        setup(**config.todict())

    else:
        setuptools.setup(
            name=package_name,
            version=version,
            packages=packages,
            scripts=scripts,
            long_description=long_description,

            package_data=package_data,
            include_package_data=True,

            install_requires=requirements,
            dependency_links=dependency_links,

            author=author,
            author_email=author_email,
            test_suite=test_suite,
        )
