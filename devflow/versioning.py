#!/usr/bin/env python
#
# Copyright (C) 2012, 2013 GRNET S.A. All rights reserved.
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

"""Helper functions for automatic version computation.

This module contains helper functions for extracting information
from a Git repository, and computing the python and debian version
of the repository code.

"""

import os
import re
import sys

from distutils import log  # pylint: disable=E0611

from devflow import BRANCH_TYPES, BASE_VERSION_FILE, VERSION_RE
from devflow import utils


DEFAULT_VERSION_FILE = """
__version__ = "%(DEVFLOW_VERSION)s"
__version_vcs_info__ = {
    'branch': '%(DEVFLOW_BRANCH)s',
    'revid': '%(DEVFLOW_REVISION_ID)s',
    'revno': %(DEVFLOW_REVISION_NUMBER)s}
__version_user_email__ = "%(DEVFLOW_USER_EMAIL)s"
__version_user_name__ = "%(DEVFLOW_USER_NAME)s"
"""


def get_base_version(vcs_info):
    """Determine the base version from a file in the repository"""

    f = open(os.path.join(vcs_info.toplevel, BASE_VERSION_FILE))
    lines = [l.strip() for l in f.readlines()]
    lines = [l for l in lines if not l.startswith("#")]
    if len(lines) != 1:
        raise ValueError("File '%s' should contain a single non-comment line.")
    f.close()
    return lines[0]


def python_version(base_version, vcs_info, mode):
    """Generate a Python distribution version following devtools conventions.

    This helper generates a Python distribution version from a repository
    commit, following devtools conventions. The input data are:
        * base_version: a base version number, presumably stored in text file
          inside the repository, e.g., /version
        * vcs_info: vcs information: current branch name and revision no
        * mode: "snapshot", or "release"

    This helper assumes a git branching model following:
    http://nvie.com/posts/a-successful-git-branching-model/

    with 'master', 'develop', 'release-X', 'hotfix-X' and 'feature-X' branches.

    General rules:
    a) any repository commit can get as a Python version
    b) a version is generated either in 'release' or in 'snapshot' mode
    c) the choice of mode depends on the branch, see following table.

    A python version is of the form A_NNN,
    where A: X.Y.Z{,next,rcW} and NNN: a revision number for the commit,
    as returned by vcs_info().

    For every combination of branch and mode, releases are numbered as follows:

    BRANCH:  /  MODE: snapshot        release
    --------          ------------------------------
    feature           0.14next_150    N/A
    develop           0.14next_151    N/A
    release           0.14rc2_249     0.14rc2
    master            N/A             0.14
    hotfix            0.14.1rc6_121   0.14.1rc6
                      N/A             0.14.1

    The suffix 'next' in a version name is used to denote the upcoming version,
    the one being under development in the develop and release branches.
    Version '0.14next' is the version following 0.14, and only lives on the
    develop and feature branches.

    The suffix 'rc' is used to denote release candidates. 'rc' versions live
    only in release and hotfix branches.

    Suffixes 'next' and 'rc' have been chosen to ensure proper ordering
    according to setuptools rules:

        http://www.python.org/dev/peps/pep-0386/#setuptools

    Every branch uses a value for A so that all releases are ordered based
    on the branch they came from, so:

    So
        0.13next < 0.14rcW < 0.14 < 0.14next < 0.14.1

    and

    >>> V("0.14next") > V("0.14")
    True
    >>> V("0.14next") > V("0.14rc7")
    True
    >>> V("0.14next") > V("0.14.1")
    False
    >>> V("0.14rc6") > V("0.14")
    False
    >>> V("0.14.2rc6") > V("0.14.1")
    True

    The value for _NNN is chosen based of the revision number of the specific
    commit. It is used to ensure ascending ordering of consecutive releases
    from the same branch. Every version of the form A_NNN comes *before*
    than A: All snapshots are ordered so they come before the corresponding
    release.

    So
        0.14next_* < 0.14
        0.14.1_* < 0.14.1
        etc

    and

    >>> V("0.14next_150") < V("0.14next")
    True
    >>> V("0.14.1next_150") < V("0.14.1next")
    True
    >>> V("0.14.1_149") < V("0.14.1")
    True
    >>> V("0.14.1_149") < V("0.14.1_150")
    True

    Combining both of the above, we get
       0.13next_* < 0.13next < 0.14rcW_* < 0.14rcW < 0.14_* < 0.14
       < 0.14next_* < 0.14next < 0.14.1_* < 0.14.1

    and

    >>> V("0.13next_102") < V("0.13next")
    True
    >>> V("0.13next") < V("0.14rc5_120")
    True
    >>> V("0.14rc3_120") < V("0.14rc3")
    True
    >>> V("0.14rc3") < V("0.14_1")
    True
    >>> V("0.14_120") < V("0.14")
    True
    >>> V("0.14") < V("0.14next_20")
    True
    >>> V("0.14next_20") < V("0.14next")
    True

    Note: one of the tests above fails because of constraints in the way
    setuptools parses version numbers. It does not affect us because the
    specific version format that triggers the problem is not contained in the
    table showing allowed branch / mode combinations, above.


    """

    branch = vcs_info.branch

    brnorm = utils.normalize_branch_name(branch)
    btypestr = utils.get_branch_type(branch)

    try:
        btype = BRANCH_TYPES[btypestr]
    except KeyError:
        allowed_branches = ", ".join(x for x in BRANCH_TYPES.keys())
        raise ValueError("Malformed branch name '%s', cannot classify as one "
                         "of %s" % (btypestr, allowed_branches))

    if btype.versioned:
        try:
            bverstr = brnorm.split("-")[1]
        except IndexError:
            # No version
            raise ValueError("Branch name '%s' should contain version" %
                             branch)

        # Check that version is well-formed
        if not re.match(VERSION_RE, bverstr):
            raise ValueError("Malformed version '%s' in branch name '%s'" %
                             (bverstr, branch))

    m = re.match(btype.allowed_version_re, base_version)
    if not m or (btype.versioned and m.groupdict()["bverstr"] != bverstr):
        raise ValueError("Base version '%s' unsuitable for branch name '%s'" %
                         (base_version, branch))

    if mode not in ["snapshot", "release"]:
        raise ValueError("Specified mode '%s' should be one of 'snapshot' or "
                         "'release'" % mode)
    snap = (mode == "snapshot")

    if (snap and not btype.builds_snapshot) or\
       (not snap and not btype.builds_release):  # nopep8
        raise ValueError("Invalid mode '%s' in branch type '%s'" %
                         (mode, btypestr))

    if snap:
        v = "%s_%d_%s" % (base_version, vcs_info.revno, vcs_info.revid)
    else:
        v = base_version
    return v


def debian_version_from_python_version(pyver):
    """Generate a debian package version from a Python version.

    This helper generates a Debian package version from a Python version,
    following devtools conventions.

    Debian sorts version strings differently compared to setuptools:
    http://www.debian.org/doc/debian-policy/ch-controlfields.html#s-f-Version

    Initial tests:

    >>> debian_version("3") < debian_version("6")
    True
    >>> debian_version("3") < debian_version("2")
    False
    >>> debian_version("1") == debian_version("1")
    True
    >>> debian_version("1") != debian_version("1")
    False
    >>> debian_version("1") >= debian_version("1")
    True
    >>> debian_version("1") <= debian_version("1")
    True

    This helper defines a 1-1 mapping between Python and Debian versions,
    with the same ordering.

    Debian versions are ordered in the same way as Python versions:

    >>> D("0.14next") > D("0.14")
    True
    >>> D("0.14next") > D("0.14rc7")
    True
    >>> D("0.14next") > D("0.14.1")
    False
    >>> D("0.14rc6") > D("0.14")
    False
    >>> D("0.14.2rc6") > D("0.14.1")
    True

    and

    >>> D("0.14next_150") < D("0.14next")
    True
    >>> D("0.14.1next_150") < D("0.14.1next")
    True
    >>> D("0.14.1_149") < D("0.14.1")
    True
    >>> D("0.14.1_149") < D("0.14.1_150")
    True

    and

    >>> D("0.13next_102") < D("0.13next")
    True
    >>> D("0.13next") < D("0.14rc5_120")
    True
    >>> D("0.14rc3_120") < D("0.14rc3")
    True
    >>> D("0.14rc3") < D("0.14_1")
    True
    >>> D("0.14_120") < D("0.14")
    True
    >>> D("0.14") < D("0.14next_20")
    True
    >>> D("0.14next_20") < D("0.14next")
    True

    """
    version = pyver.replace("_", "~").replace("rc", "~rc")
    codename = utils.get_distribution_codename()
    minor = str(get_revision(version, codename))
    return version + "-" + minor + "~" + codename


def get_revision(version, codename):
    """Find revision for a debian version"""
    version_tag = utils.version_to_tag(version)
    repo = utils.get_repository()
    minor = 1
    while True:
        tag = "debian/" + version_tag + "-" + str(minor) + codename
        if tag in repo.tags:
            minor += 1
        else:
            return minor


def get_python_version():
    v = utils.get_vcs_info()
    b = get_base_version(v)
    mode = utils.get_build_mode()
    return python_version(b, v, mode)


def debian_version(base_version, vcs_info, mode):
    p = python_version(base_version, vcs_info, mode)
    return debian_version_from_python_version(p)


def get_debian_version():
    v = utils.get_vcs_info()
    b = get_base_version(v)
    mode = utils.get_build_mode()
    return debian_version(b, v, mode)


def update_version():
    """Generate or replace version files

    Helper function for generating/replacing version files containing version
    information.

    """

    v = utils.get_vcs_info()
    toplevel = v.toplevel

    config = utils.get_config()
    if not v:
        # Return early if not in development environment
        raise RuntimeError("Can not compute version outside of a git"
                           " repository.")
    b = get_base_version(v)
    mode = utils.get_build_mode()
    version = python_version(b, v, mode)
    debian_version_ = debian_version_from_python_version(version)
    env = {"DEVFLOW_VERSION": version,
           "DEVFLOW_DEBIAN_VERSION": debian_version_,
           "DEVFLOW_BRANCH": v.branch,
           "DEVFLOW_REVISION_ID": v.revid,
           "DEVFLOW_REVISION_NUMBER": v.revno,
           "DEVFLOW_USER_EMAIL": v.email,
           "DEVFLOW_USER_NAME": v.name}

    for _pkg_name, pkg_info in config['packages'].items():
        version_filename = pkg_info.get('version_file')
        if not version_filename:
            continue
        version_template = pkg_info.get('version_template')
        if version_template:
            vtemplate_file = os.path.join(toplevel, version_template)
            try:
                with file(vtemplate_file) as f:
                    content = f.read(-1) % env
            except IOError as e:
                if e.errno == 2:
                    raise RuntimeError("devflow.conf contains '%s' as a"
                                       " version template file, but file does"
                                       " not exists!" % vtemplate_file)
                else:
                    raise
        else:
            content = DEFAULT_VERSION_FILE % env
        with file(os.path.join(toplevel, version_filename), 'w+') as f:
            log.info("Updating version file '%s'" % version_filename)
            f.write(content)


def bump_version_main():
    try:
        version = sys.argv[1]
        bump_version(version)
    except IndexError:
        sys.stdout.write("Give me a version %s!\n")
        sys.stdout.write("usage: %s version\n" % sys.argv[0])


def bump_version(new_version):
    """Set new base version to base version file and commit"""
    v = utils.get_vcs_info()
    mode = utils.get_build_mode()

    # Check that new base version is valid
    python_version(new_version, v, mode)

    repo = utils.get_repository()
    toplevel = repo.working_dir

    old_version = get_base_version(v)
    sys.stdout.write("Current base version is '%s'\n" % old_version)

    version_file = os.path.join(toplevel, "version")
    sys.stdout.write("Updating version file %s from version '%s' to '%s'\n"
                     % (version_file, old_version, new_version))

    f = open(version_file, 'rw+')
    lines = f.readlines()
    for i in range(0, len(lines)):
        if not lines[i].startswith("#"):
            lines[i] = lines[i].replace(old_version, new_version)
    f.seek(0)
    f.truncate(0)
    f.writelines(lines)
    f.close()

    repo.git.add(version_file)
    repo.git.commit(m="Bump version to %s" % new_version)
    sys.stdout.write("Update version file and commited\n")


def main():
    v = utils.get_vcs_info()
    b = get_base_version(v)
    mode = utils.get_build_mode()

    try:
        arg = sys.argv[1]
        assert arg == "python" or arg == "debian"
    except IndexError:
        raise ValueError("A single argument, 'python' or 'debian is required")

    if arg == "python":
        print python_version(b, v, mode)
    elif arg == "debian":
        print debian_version(b, v, mode)

if __name__ == "__main__":
    sys.exit(main())
