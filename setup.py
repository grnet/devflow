# Copyright 2012, 2013 GRNET S.A. All rights reserved.
#
# Redistribution and use in source and binary forms, with or
# without modification, are permitted provided that the following
# conditions are met:
#
#   1. Redistributions of source code must retain the above
#      copyright notice, this list of conditions and the following
#      disclaimer.
#
#   2. Redistributions in binary form must reproduce the above
#      copyright notice, this list of conditions and the following
#      disclaimer in the documentation and/or other materials
#      provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY GRNET S.A. ``AS IS'' AND ANY EXPRESS
# OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL GRNET S.A OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF
# USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED
# AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and
# documentation are those of the authors and should not be
# interpreted as representing official policies, either expressed
# or implied, of GRNET S.A.
#
import os
from setuptools import setup, find_packages

try:
    from devflow.version import __version__
except ImportError:
    # Bootstrap devflow
    from devflow.versioning import update_version
    update_version()
    from devflow.version import __version__

HERE = os.path.abspath(os.path.normpath(os.path.dirname(__file__)))

# Package info
VERSION = __version__
README = open(os.path.join(HERE, 'README.md')).read()
CHANGES = open(os.path.join(HERE, 'Changelog')).read()
SHORT_DESCRIPTION = 'A set of tools to ease versioning and use of git flow.'

PACKAGES_ROOT = '.'
PACKAGES = find_packages(PACKAGES_ROOT)

# Package meta
CLASSIFIERS = []

# Package requirements
INSTALL_REQUIRES = ['gitpython>=0.3.2RC1', 'sh', 'configobj', 'ansicolors']

# Provided as an attribute, so you can append to these instead
# of replicating them:
standard_exclude = ["*.py", "*.pyc", "*$py.class", "*~", ".*", "*.bak"]
standard_exclude_directories = [".*", "CVS", "_darcs", "./build", "./dist",
                                "EGG-INFO", "*.egg-info"]

setup(
    name='devflow',
    version=VERSION,
    license='BSD',
    url='http://www.synnefo.org/',
    description=SHORT_DESCRIPTION,
    long_description=README + '\n\n' + CHANGES,
    classifiers=CLASSIFIERS,

    author='Synnefo development team',
    author_email='synnefo-devel@googlegroups.com',
    maintainer='Synnefo development team',
    maintainer_email='synnefo-devel@googlegroups.com',

    packages=find_packages(),
    include_package_data=True,

    install_requires=INSTALL_REQUIRES,

    entry_points={
        'console_scripts': [
            'devflow-version=devflow.versioning:main',
            'devflow-bump-version=devflow.versioning:bump_version_main',
            'devflow-update-version=devflow.versioning:update_version',
            'devflow-autopkg=devflow.autopkg:main',
            'devflow-flow=devflow.flow:main'],
    },
)
