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
from collections import namedtuple


def get_repository():
    """Load the repository from the current working dir."""

    try:
        return git.Repo(".")
    except git.InvalidGitRepositoryError:
        msg = "Cound not retrivie git information. Directory '%s'"\
              " is not a git repository!" % os.getcwd()
        raise RuntimeError(msg)


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
    if branch == "master":
        return "debian"
    # Check if debian-branch exists (local or origin)
    deb_branch = "debian-" + branch
    if _get_branch(deb_branch) or _get_branch("origin/" + deb_branch):
        return deb_branch
    return "debian"


def _get_branch(branch):
    repo = get_repository()
    if branch in repo.branches:
        return branch
    origin_branch = "origin/" + branch
    if origin_branch in repo.refs:
        print "Creating branch '%s' to track '%s'" (branch, origin_branch)
        repo.git.branch(branch, origin_branch)
        return branch
    else:
        return None
