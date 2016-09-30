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

"""A set of tools to ease versioning and use of git flow"""

from collections import namedtuple

# Branch types:
# builds_snapshot: Whether the branch can produce snapshot builds
# builds_release: Whether the branch can produce release builds
# versioned: Whether the name of the branch defines a specific version
# allowed_version_re: A regular expression describing allowed values for
#                     base_version in this branch
branch_type = namedtuple("branch_type", ["builds_snapshot", "builds_release",
                                         "versioned", "allowed_version_re",
                                         "debian_branch"])
VERSION_RE = r'[0-9]+\.[0-9]+(\.[0-9]+)*'
RC_RE = r'rc[1-9][0-9]*'

BRANCH_TYPES = {
    "feature": branch_type(True, False, False,
                           "^%s(next|\.?dev)?$" % VERSION_RE,
                           "debian-develop"),
    "develop": branch_type(True, False, False,
                           "^%s(next|\.?dev)?$" % VERSION_RE,
                           "debian-develop"),
    "release": branch_type(True, True, True,
                           "^(?P<bverstr>%s)(%s)+$" % (VERSION_RE, RC_RE),
                           "debian-develop"),
    "master": branch_type(True, True, False,
                          "^%s$" % VERSION_RE, "debian"),
    "hotfix": branch_type(True, True, True,
                          r"^(?P<bverstr>^%s\.[1-9][0-9]*)(%s)*$" %
                          (VERSION_RE, RC_RE),
                          "debian")}
BASE_VERSION_FILE = "version"
