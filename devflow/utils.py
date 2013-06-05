# Copyright (C) 2013 GRNET S.A. All rights reserved.
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

import os
import git
import sh
from collections import namedtuple
from configobj import ConfigObj

from devflow import BRANCH_TYPES


def get_repository(path=None):
    """Load the repository from the current working dir."""
    if path is None:
        path = os.getcwd()
    try:
        return git.Repo(path)
    except git.InvalidGitRepositoryError:
        msg = "Cound not retrivie git information. Directory '%s'"\
              " is not a git repository!" % path
        raise RuntimeError(msg)


def get_config(path=None):
    """Load configuration file."""
    if path is None:
        toplevel = get_vcs_info().toplevel
        path = os.path.join(toplevel, "devflow.conf")

    config = ConfigObj(path)
    return config


def get_vcs_info():
    """Return current git HEAD commit information.

    Returns a tuple containing
        - branch name
        - commit id
        - commit count
        - git describe output
        - path of git toplevel directory

    """

    repo = get_repository()
    branch = repo.head.reference
    revid = get_commit_id(branch.commit, branch)
    revno = len(list(repo.iter_commits()))
    toplevel = repo.working_dir

    info = namedtuple("vcs_info", ["branch", "revid", "revno",
                                   "toplevel"])

    return info(branch=branch.name, revid=revid, revno=revno,
                toplevel=toplevel)


def get_commit_id(commit, current_branch):
    """Return the commit ID

    If the commit is a 'merge' commit, and one of the parents is a
    debian branch we return a compination of the parents commits.

    """
    def short_id(commit):
        return commit.hexsha[0:7]

    parents = commit.parents
    cur_br_name = current_branch.name
    if len(parents) == 1:
        return short_id(commit)
    elif len(parents) == 2:
        if cur_br_name.startswith("debian-") or cur_br_name == "debian":
            pr1, pr2 = parents
            return short_id(pr1) + "_" + short_id(pr2)
        else:
            return short_id(commit)
    else:
        raise RuntimeError("Commit %s has more than 2 parents!" % commit)


def get_debian_branch(branch):
    """Find the corresponding debian- branch"""
    distribution = get_distribution_codename()
    repo = get_repository()
    if branch == "master":
        deb_branch = "debian-" + distribution
    else:
        deb_branch = "-".join(["debian", branch, distribution])
    # Check if debian-branch exists (local or origin)
    if _get_branch(deb_branch):
        return deb_branch
    # Check without distribution
    deb_branch = deb_branch.rstrip("-" + distribution)
    if _get_branch(deb_branch):
        return deb_branch
    branch_type = BRANCH_TYPES[get_branch_type(branch)]
    # If not try the default debian branch with distribution
    default_branch = branch_type.debian_branch + "-" + distribution
    if _get_branch(default_branch):
        repo.git.branch(deb_branch, default_branch)
        print "Created branch '%s' from '%s'" % (deb_branch, default_branch)
        return deb_branch
    # And without distribution
    default_branch = branch_type.debian_branch
    if _get_branch(default_branch):
        repo.git.branch(deb_branch, default_branch)
        print "Created branch '%s' from '%s'" % (deb_branch, default_branch)
        return deb_branch
    # If not try the debian branch
    repo.git.branch(deb_branch, default_branch)
    print "Created branch '%s' from 'debian'" % deb_branch
    return "debian"


def _get_branch(branch):
    repo = get_repository()
    if branch in repo.branches:
        return branch
    origin_branch = "origin/" + branch
    if origin_branch in repo.refs:
        print "Creating branch '%s' to track '%s'" % (branch, origin_branch)
        repo.git.branch(branch, origin_branch)
        return branch
    else:
        return None


def get_build_mode():
    """Determine the build mode"""
    # Get it from environment if exists
    mode = os.environ.get("DEVFLOW_BUILD_MODE", None)
    if mode is None:
        branch = get_branch_type(get_vcs_info().branch)
        try:
            br_type = BRANCH_TYPES[get_branch_type(branch)]
        except KeyError:
            allowed_branches = ", ".join(x for x in BRANCH_TYPES.keys())
            raise ValueError("Malformed branch name '%s', cannot classify as"
                             " one of %s" % (branch, allowed_branches))
        mode = "snapshot" if br_type.builds_snapshot else "release"
    return mode


def normalize_branch_name(branch_name):
    """Normalize branch name by removing debian- if exists"""
    brnorm = branch_name
    if brnorm == "debian":
        brnorm = "debian-master"
    # If it's a debian branch, ignore starting "debian-"
    if brnorm.startswith("debian-"):
        brnorm = brnorm.replace("debian-", "", 1)
    return brnorm


def get_branch_type(branch_name):
    """Extract the type from a branch name"""
    branch_name = normalize_branch_name(branch_name)
    if "-" in branch_name:
        btypestr = branch_name.split("-")[0]
    else:
        btypestr = branch_name
    return btypestr


def version_to_tag(version):
    return version.replace("~", "")


def undebianize(branch):
    if branch == "debian":
        return "master"
    elif branch.startswith("debian-"):
        return branch.replace("debian-", "")
    else:
        return branch


def get_distribution_codename():
    output = sh.lsb_release("-c")
    _, codename = output.split("\t")
    codename = codename.strip()
    return codename
