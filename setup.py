# Copyright 2012-2016 GRNET S.A. All rights reserved.
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
from imp import load_source

HERE = os.path.abspath(os.path.normpath(os.path.dirname(__file__)))
VERSION = os.path.join(HERE, 'devflow', 'version.py')

# Package info
README = open(os.path.join(HERE, 'README.md')).read()
CHANGES = open(os.path.join(HERE, 'Changelog')).read()
SHORT_DESCRIPTION = 'A set of tools to ease versioning and use of git flow.'

# Package meta
CLASSIFIERS = [
    'Environment :: Console',
    'License :: OSI Approved :: BSD License',
    'Programming Language :: Python',
    'Programming Language :: Python :: 2 :: Only',
    'Topic :: Software Development',
    'Topic :: Software Development :: Build Tools']

# Package requirements
INSTALL_REQUIRES = ['gitpython>=0.3.2RC1', 'sh', 'configobj', 'ansicolors']

setup(
    name='devflow',
    version=getattr(load_source('version', VERSION), "__version__"),
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
