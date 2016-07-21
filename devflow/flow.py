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

import os
import re
import subprocess

import logging
logging.basicConfig()

from argparse import ArgumentParser

os.environ["GIT_PYTHON_TRACE"] = "full"
from devflow import utils, versioning, RC_RE
from devflow.version import __version__
from devflow.ui import query_action, query_user, query_yes_no
from functools import wraps, partial
from contextlib import contextmanager
from git.exc import GitCommandError
from sh import mktemp


def create_temp_file(suffix):
    create_dir_cmd = mktemp("/tmp/" + suffix + "-XXXXX")
    return create_dir_cmd.stdout.strip()


def cleanup(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except:
            self.log.debug("Unexpected ERROR. Cleaning up repository...")
            self.repo.git.reset("--hard", "HEAD")
            self.repo.git.checkout(self.start_branch)
            self.repo.git.reset("--hard", self.start_hex)
            for branch in self.new_branches:
                self.repo.git.branch("-D", branch)
            for tag in self.new_tags:
                self.repo.git.tag("-D", tag)
            raise
    return wrapper


@contextmanager
def conflicts():
    try:
        yield
    except GitCommandError as e:
        if e.status != 128:
            print "An error occured. Resolve it and type 'exit 0'"
            tmpbashrc = create_temp_file("bashrc")
            f = open(tmpbashrc, 'w')
            f.write("source $HOME/.bashrc ; export PS1=(Conflict)\"$PS1\"")
            f.close()
            subprocess.check_call(['bash', '--rcfile', tmpbashrc])
            os.unlink(tmpbashrc)
        else:
            raise


def get_release_version(develop_version):
    '''Given a development version it will return the release version'''

    # Old version scheme
    if 'next' in develop_version:
        version = develop_version.rstrip('next')
        parts = version.split('.')
        major = int(parts[0])
        minor = int(parts[1])
        return "%d.%d" % (major, minor+1)

    # New version may or may not contain dev:
    #   0.19 is fine, same as 0.19.dev or 0.19dev
    return develop_version.rstrip('.dev').rstrip('dev')


def get_develop_version_from_release(release_version):
    '''Given a release version it will return the next develop version'''
    # version = re.sub('rc[0-9]+$', '', release_version)
    version = release_version
    parts = version.split('.')
    major = int(parts[0])
    minor = int(parts[1])
    return "%d.%ddev" % (major, minor+1)


def get_hotfix_version(version):
    """Given a version it will return the next hotfix version"""
    parts = version.split('.')
    major = int(parts[0])
    minor = int(parts[1])
    hotfix = int(parts[2]) if len(parts) > 2 else 0

    return "%d.%d.%d" % (major, minor, hotfix+1)


class GitManager(object):
    def __init__(self):
        self.repo = utils.get_repository()
        self.start_branch = self.repo.active_branch.name
        self.start_hex = self.repo.head.log()[-1].newhexsha
        self.log = logging.getLogger("")
        self.log.setLevel(logging.DEBUG)
        self.log.info("Repository: %s. HEAD: %s", self.repo, self.start_hex)
        self.new_branches = []
        self.new_tags = []
        # self.repo.git.pull("origin")

        # Check if version is obsolete
        versioning.check_obsolete_version()


    def get_branch(self, mode, version):
        if mode not in ["release", "hotfix"]:
            raise ValueError("Unknown mode: %s" % mode)
        return "%s-%s" % (mode, version)

    def get_debian_branch(self, mode, version):
        if mode not in ["release", "hotfix"]:
            raise ValueError("Unknown mode: %s" % mode)
        return "debian-%s-%s" % (mode, version)

    def doit(self, action_yes=None, action_no=None, question="Do it",
             args=None, default=False):
        if not args.defaults:
            ret = query_yes_no(question, default="yes" if default else "no")
        else:
            ret = default

        if ret and action_yes:
            action_yes()
        elif not ret and action_no:
            action_no()

    def __print_cleanup(self, branches):
        print "To remove obsolete branches run:"
        for b in branches:
            print "git branch -D %s" % b

    def __cleanup_branches(self, branches):
        repo = self.repo
        for b in branches:
            repo.git.branch("-D", b)

    def cleanup_branches(self, branches, args, default=False):
        if args.cleanup is not None:
            if args.cleanup:
                self.__cleanup_branches(branches)
            else:
                self.__print_cleanup(branches)
            return

        question = "Remove branches %s" % branches
        action_yes = partial(self.__cleanup_branches, branches)
        action_no = partial(self.__print_cleanup, branches)
        self.doit(action_yes=action_yes, action_no=action_no,
                  question=question, args=args, default=default)

    def check_edit_changelog(self, edit_action, args, default=True):
        if args.edit_changelog is not None:
            if args.edit_changelog:
                edit_action()
            return
        question = "Edit changelog ?"
        self.doit(action_yes=edit_action, question=question, args=args,
                  default=default)

    def _merge_branches(self, branch_to, branch_from):
        repo = self.repo
        cur_branch = repo.active_branch.name
        repo.git.checkout(branch_to)
        with conflicts():
            repo.git.merge("--no-ff", branch_from)
        repo.git.checkout(cur_branch)

    def merge_branches(self, branch_to, branch_from, args, default=True):
        action = partial(self._merge_branches, branch_to, branch_from)
        question = "Merge branch %s to %s ?" % (branch_from, branch_to)
        self.doit(action_yes=action, question=question, args=args,
                  default=default)

    def edit_changelog(self, branch, base_branch=None):
        repo = self.repo
        if branch not in repo.branches:
            raise ValueError("Branch %s does not exist." % branch)
        if base_branch and base_branch not in repo.branches:
            raise ValueError("Branch %s does not exist." % base_branch)

        repo.git.checkout(branch)
        topdir = repo.working_dir
        changelog = os.path.join(topdir, "Changelog")

        lines = []
        lines.append("#Changelog for %s\n" % branch)
        if base_branch:
            commits = repo.git.rev_list(
                "%s..%s" % (base_branch, branch)).split("\n")
            for c in commits:
                commit = repo.commit(c)
                lines.append("* " + commit.message.split("\n")[0])
        lines.append("\n")

        f = open(changelog, 'r+')
        lines.extend(f.readlines())
        f.seek(0)
        f.truncate(0)
        f.writelines(lines)
        f.close()

        subprocess.check_call(['editor', changelog])
        repo.git.add(changelog)
        repo.git.commit(m="Update changelog")
        print "Updated changelog on branch %s" % branch

    @cleanup
    def start_release(self, args):
        repo = self.repo
        upstream = "develop"
        debian = "debian-develop"
        repo.git.checkout(upstream)

        vcs = utils.get_vcs_info()
        develop_version = versioning.get_base_version(vcs)
        if not args.version:
            version = get_release_version(develop_version)
            if not args.defaults:
                version = query_user("Release version", default=version)
        else:
            # validate version?
            pass
        rc_version = "%src1" % version
        new_develop_version = "%snext" % version

        upstream_branch = self.get_branch("release", version)
        debian_branch = self.get_debian_branch("release", version)

        # create release branch
        repo.git.branch(upstream_branch, upstream)
        self.new_branches.append(upstream_branch)
        repo.git.checkout(upstream_branch)
        versioning.bump_version(rc_version)

        # create debian release branch
        repo.git.checkout(debian)
        repo.git.branch(debian_branch, debian)
        self.new_branches.append(debian_branch)

        repo.git.checkout(upstream_branch)
        repo.git.checkout(debian)

        # bump develop version
        repo.git.checkout(upstream)
        versioning.bump_version(new_develop_version)

        repo.git.checkout(upstream_branch)

    @cleanup
    def start_hotfix(self, args):
        repo = self.repo
        upstream = "master"
        debian = "debian"
        repo.git.checkout(upstream)
        # maybe provide major.minor version, find the latest release/hotfix and
        # branch from there ?

        vcs = utils.get_vcs_info()
        version = versioning.get_base_version(vcs)
        if not args.version:
            version = get_hotfix_version(version)
            if not args.defaults:
                version = query_user("Hotfix version", default=version)
        else:
            # validate version?
            pass

        rc_version = "%src1" % version
        new_develop_version = "%snext" % version

        upstream_branch = self.get_branch("hotfix", version)
        debian_branch = self.get_debian_branch("hotfix", version)

        # create hotfix branch
        repo.git.branch(upstream_branch, upstream)
        self.new_branches.append(upstream_branch)
        repo.git.checkout(upstream_branch)
        versioning.bump_version(rc_version)

        # create debian hotfix branch
        repo.git.checkout(debian)
        repo.git.branch(debian_branch, debian)
        self.new_branches.append(debian_branch)

        repo.git.checkout(upstream_branch)
        repo.git.checkout(debian)

        # bump develop version. Ask first or verify we have the same
        # major.minornext?
        # repo.git.checkout(upstream)
        # versioning.bump_version(new_develop_version)

        repo.git.checkout(upstream_branch)

    @cleanup
    def end_release(self, args):
        version = args.version
        repo = self.repo
        master = "master"
        debian_master = "debian"
        upstream = "develop"
        debian = "debian-develop"
        upstream_branch = self.get_branch("release", version)
        debian_branch = self.get_debian_branch("release", version)
        tag = upstream_branch
        debian_tag = "debian/" + tag

        edit_action = partial(self.edit_changelog, upstream_branch, "develop")
        self.check_edit_changelog(edit_action, args, default=True)

        vcs = utils.get_vcs_info()
        release_version = versioning.get_base_version(vcs)
        if re.match('.*'+RC_RE, release_version):
            new_version = re.sub(RC_RE, '', release_version)
            versioning._bump_version(new_version, vcs)

        # merge to master
        self._merge_branches(master, upstream_branch)
        self._merge_branches(debian_master, debian_branch)

        # create tags
        repo.git.checkout(master)
        repo.git.tag("%s" % tag)
        repo.git.checkout(debian)
        repo.git.tag("%s" % debian_tag)

        # merge release changes to upstream
        self.merge_branches(upstream, upstream_branch, args, default=True)
        self.merge_branches(debian, debian_branch, args, default=True)

        repo.git.checkout(upstream)

        branches = [upstream_branch, debian_branch]
        self.cleanup_branches(branches, args, default=True)

    @cleanup
    def end_hotfix(self, args):
        version = args.version

        repo = self.repo
        upstream = "master"
        debian = "debian"
        upstream_branch = self.get_branch("hotfix", version)
        debian_branch = self.get_debian_branch("hotfix", version)

        # create tags?

        self._merge_branches(upstream, upstream_branch)
        self._merge_branches(debian, debian_branch)

        repo.git.checkout(upstream)

        branches = [upstream_branch, debian_branch]
        self.cleanup_branches(branches, args, default=True)

    @cleanup
    def start_feature(self, args):
        feature_name = args.feature_name
        repo = self.repo
        feature_upstream = "feature-%s" % feature_name
        feature_debian = "debian-%s" % feature_upstream
        repo.git.branch(feature_upstream, "develop")
        self.new_branches.append(feature_upstream)
        repo.git.branch(feature_debian, "debian-develop")
        self.new_branches.append(feature_debian)

    @cleanup
    def end_feature(self, args):
        feature_name = args.feature_name
        repo = self.repo
        feature_upstream = "feature-%s" % feature_name
        if feature_upstream not in repo.branches:
            raise ValueError("Branch %s does not exist." % feature_upstream)
        feature_debian = "debian-%s" % feature_upstream

        edit_action = partial(self.edit_changelog, feature_upstream, "develop")
        self.check_edit_changelog(edit_action, args, default=True)

        # merge to develop
        self._merge_branches("develop", feature_upstream)
        if feature_debian in repo.branches:
            self._merge_branches("debian-develop", feature_debian)
        repo.git.checkout("develop")

        branches = [feature_upstream]
        if feature_debian in repo.branches:
            branches.append(feature_debian)
        self.cleanup_branches(branches, args, default=True)


def refhead(repo):
    return repo.head.log[-1].newhexsha


def main():
    parser = ArgumentParser(description="Devflow tool")
    parser.add_argument('-V', '--version', action='version',
                        version='devflow-flow %s' % __version__)
    parser.add_argument(
        '-d', '--defaults', action='store_true', default=False,
        help="Assume default on every choice, unless a value is provided")

    subparsers = parser.add_subparsers()

    init_parser = subparsers.add_parser('init',
                                        help="Initialize a new devflow repo")
    init_parser.add_argument('-m', '--master', type=str, nargs='?',
                             help="Master branch")
    init_parser.add_argument('-d', '--develop', type=str, nargs='?',
                             help="Develop branch")
    init_parser.set_defaults(func='init_repo')

    feature_parser = subparsers.add_parser('feature', help="Feature options")
    feature_subparsers = feature_parser.add_subparsers()

    feature_start_parser = feature_subparsers.add_parser(
        'start', help="Start a new feature")
    feature_start_parser.set_defaults(func='start_feature')
    feature_start_parser.add_argument('feature_name', type=str,
                                      help="Name of the feature")

    feature_finish_parser = feature_subparsers.add_parser(
        'finish', help="Finish a feature")
    feature_finish_parser.set_defaults(func='end_feature')
    feature_finish_parser.add_argument('feature_name', type=str,
                                       help="Name of the feature")
    feature_finish_parser.add_argument(
        '--no-edit-changelog', action='store_const', const=False,
        dest='edit_changelog', help="Do not edit the changelog")
    feature_finish_parser.add_argument(
        '--no-cleanup', action='store_const', const=True, dest='cleanup',
        help="Do not cleanup branches")

    release_parser = subparsers.add_parser('release', help="release options")
    release_subparsers = release_parser.add_subparsers()

    release_start_parser = release_subparsers.add_parser(
        'start', help="Start a new release")
    release_start_parser.add_argument(
        '--version', type=str, help="Version of the release")
    release_start_parser.add_argument(
        '--develop-version', type=str, help="New develop version")
    release_start_parser.set_defaults(func='start_release')

    release_finish_parser = release_subparsers.add_parser(
        'finish', help="Finish a release")
    release_finish_parser.add_argument(
        'version', type=str, help="Version of the release")
    release_finish_parser.add_argument(
        '--no-edit-changelog', action='store_const', const=False,
        dest='edit_changelog', help="Do not edit the changelog")
    release_finish_parser.add_argument(
        '--no-cleanup', action='store_const', const=True, dest='cleanup',
        help="Do not cleanup branches")

    release_finish_parser.set_defaults(func='end_release')

    hotfix_parser = subparsers.add_parser('hotfix', help="hotfix options")
    hotfix_subparsers = hotfix_parser.add_subparsers()

    hotfix_start_parser = hotfix_subparsers.add_parser(
        'start', help="Start a new hotfix")
    hotfix_start_parser.add_argument(
        '--version', type=str, help="Version of the hotfix")
    hotfix_start_parser.add_argument(
        '--develop-version', type=str, help="New develop version")
    hotfix_start_parser.set_defaults(func='start_hotfix')

    hotfix_finish_parser = hotfix_subparsers.add_parser(
        'finish', help="Finish a hotfix")
    hotfix_finish_parser.add_argument(
        'version', type=str, help="Version of the hotfix")
    hotfix_finish_parser.add_argument(
        '--no-edit-changelog', action='store_const', const=False,
        dest='edit_changelog', help="Do not edit the changelog")
    hotfix_finish_parser.add_argument(
        '--no-cleanup', action='store_const', const=True, dest='cleanup',
        help="Do not cleanup branches")
    hotfix_finish_parser.set_defaults(func='end_hotfix')

    args = parser.parse_args()

    gm = GitManager()
    getattr(gm, args.func)(args)


if __name__ == "__main__":
    main()
