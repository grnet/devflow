import os

import logging
logging.basicConfig()
from optparse import OptionParser

os.environ["GIT_PYTHON_TRACE"] = "full"
from devflow import utils, versioning
from devflow.version import __version__
from devflow.autopkg import call
from functools import wraps
from contextlib import contextmanager
from git.exc import GitCommandError


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
            print "An error occured. Resolve it and type 'exit'"
            call("bash")
        else:
            raise


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
        self.repo.git.pull("origin")

    @cleanup
    def start_release(self, version):
        self.start_common("release", version)

    @cleanup
    def start_hotfix(self, version):
        self.start_common("hotfix", version)

    @cleanup
    def end_release(self, version):
        self.end_common("release", version)

    @cleanup
    def end_hotfix(self, version):
        self.end_common("hotfix", version)

    def start_common(self, mode, version):
        if mode not in ["release", "hotfix"]:
            raise ValueError("Unknown mode: %s" % mode)
        repo = self.repo
        upstream = "develop" if mode == "release" else "master"
        debian = "debian-develop" if mode == "release" else "debian"
        upstream_branch = "%s-%s" % (mode, version)
        debian_branch = "debian-%s-%s" % (mode, version)
        repo.git.checkout(upstream)
        repo.git.branch(upstream_branch, upstream)
        self.new_branches.append(upstream_branch)
        versioning.bump_version("%snext" % version)
        repo.git.checkout(upstream_branch)
        versioning.bump_version("%src1" % version)
        repo.git.checkout(debian)
        repo.git.branch(debian_branch, debian)
        self.new_branches.append(debian_branch)
        repo.git.checkout(upstream_branch)
        repo.git.checkout(debian)

    @cleanup
    def start_feature(self, feature_name):
        repo = self.repo
        feature_upstream = "feature-%s" % feature_name
        feature_debian = "debian-%s" % feature_upstream
        repo.git.branch(feature_upstream, "develop")
        self.new_branches.append(feature_upstream)
        repo.git.branch(feature_debian, "debian-develop")
        self.new_branches.append(feature_debian)

    @cleanup
    def end_feature(self, feature_name):
        repo = self.repo
        feature_upstream = "feature-%s" % feature_name
        if not feature_upstream in repo.branches:
            raise ValueError("Branch %s does not exist." % feature_upstream)
        feature_debian = "debian-%s" % feature_upstream
        repo.git.checkout("develop")
        with conflicts():
            repo.git.merge(feature_upstream)
        repo.git.checkout("debian-develop")
        if feature_debian in repo.branches:
            with conflicts():
                repo.git.merge(feature_debian)
        repo.git.checkout("develop")
        print "To remove obsolete branches run:"
        print "git branch -D %s" % feature_upstream
        if feature_debian in repo.branches:
            print "git branch -D %s" % feature_debian

    def end_common(self, mode, version):
        if mode not in ["release", "hotfix"]:
            raise ValueError("Unknown mode: %s" % mode)
        repo = self.repo
        master = "master"
        upstream = "develop" if mode == "release" else "master"
        debian = "debian-develop" if mode == "release" else "debian"
        upstream_branch = "%s-%s" % (mode, version)
        debian_branch = "debian-%s-%s" % (mode, version)
        repo.git.checkout(upstream)
        with conflicts():
            repo.git.merge("--no-ff", upstream_branch)
        repo.git.checkout(master)
        with conflicts():
            repo.git.merge("--no-ff", upstream_branch)
        repo.git.checkout(debian)
        with conflicts():
            repo.git.merge("--no-ff", debian_branch)
        repo.git.checkout(upstream)
        print "To remove obsolete branches run:"
        print "git branch -d %s" % upstream_branch
        print "git branch -d %s" % debian_branch


def refhead(repo):
    return repo.head.log[-1].newhexsha


def main():
    HELP_MSG = "usage: %prog mode=[release|hotfix|feature]"\
               " [version|name]"
    parser = OptionParser(usage=HELP_MSG,
                          version="devflow-flow %s" % __version__,
                          add_help_option=True)
    options, args = parser.parse_args()
    if len(args) != 3:
        parser.error("Invalid number of arguments.")
    mode, action, version = args
    gm = GitManager()
    func = "%s_%s" % (action, mode)
    try:
        getattr(gm, func)(version)
    except AttributeError:
        parser.error("Invalid arguments.")

if __name__ == "__main__":
    main()
