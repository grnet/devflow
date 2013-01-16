# Copyright 2012 GRNET S.A. All rights reserved.
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

import git
import os
import sys
from sh import mktemp, cd, rm, git_dch, python
from optparse import OptionParser

from devflow.versioning import (get_python_version,
                                debian_version_from_python_version)

try:
    from colors import red, green
except ImportError:
    red = lambda x: x
    green = lambda x: x

print_red = lambda x: sys.stdout.write(red(x) + "\n")
print_green = lambda x: sys.stdout.write(green(x) + "\n")

AVAILABLE_MODES = ["release", "snapshot"]


def get_packages_to_build(toplevel_dir):
    conf_file = os.path.join(toplevel_dir, "autopkg.conf")
    try:
        f = open(conf_file)
    except IOError:
        raise RuntimeError("Configuration file %s does not exist!" % conf_file)

    lines = [l.strip() for l in f.readlines()]
    l = [l for l in lines if not l.startswith("#")]
    f.close()
    return l


def main():
    from devflow.version import __version__
    parser = OptionParser(usage="usage: %prog [options] mode",
                          version="devflow %s" % __version__)
    parser.add_option("-k", "--keep-repo",
                      action="store_true",
                      dest="keep_repo",
                      default=False,
                      help="Do not delete the cloned repository")
    parser.add_option("-b", "--build-dir",
                      dest="build_dir",
                      default=None,
                      help="Directory to store created pacakges")
    parser.add_option("-r", "--repo-dir",
                      dest="repo_dir",
                      default=None,
                      help="Directory to clone repository")
    parser.add_option("-d", "--dirty",
                      dest="force_dirty",
                      default=False,
                      action="store_true",
                      help="Do not check if working directory is dirty")

    (options, args) = parser.parse_args()

    try:
        mode = args[0]
    except IndexError:
        raise ValueError("Mode argument is mandatory. Usage: %s"
                         % parser.usage)
    if mode not in AVAILABLE_MODES:
        raise ValueError(red("Invalid argument! Mode must be one: %s"
                         % ", ".join(AVAILABLE_MODES)))

    os.environ["GITFLOW_BUILD_MODE"] = mode

    try:
        original_repo = git.Repo(".")
    except git.git.InvalidGitRepositoryError:
        raise RuntimeError(red("Current directory is not git repository."))

    toplevel = original_repo.working_dir
    if original_repo.is_dirty() and not options.force_dirty:
        raise RuntimeError(red("Repository %s is dirty." % toplevel))

    repo_dir = options.repo_dir
    if not repo_dir:
        repo_dir = mktemp("-d", "/tmp/devflow-build-repo-XXX").stdout.strip()
        print_green("Created temporary directory '%s' for the cloned repo."
                    % repo_dir)

    packages = get_packages_to_build(toplevel)
    if packages:
        print_green("Will build the following packages:\n" + \
                    "\n".join(packages))
    else:
        raise RuntimeError("Configuration file is empty."
                           " No packages to build.")

    repo = original_repo.clone(repo_dir)
    print_green("Cloned current repository to '%s'." % repo_dir)

    reflog_hexsha = repo.head.log()[-1].newhexsha
    print "Latest Reflog entry is %s" % reflog_hexsha

    branch = repo.head.reference.name
    if branch == "master":
        debian_branch = "debian"
    else:
        debian_branch = "debian-" + branch

    if not debian_branch in repo.references:
        # Branch does not exist!
        if "origin/" + debian_branch in repo.references:
            remote = "origin/" + debian_branch
        else:
            remote = "origin/debian-develop"
        repo.git.branch("--track", debian_branch, remote)

    repo.git.checkout(debian_branch)
    print_green("Changed to branch '%s'" % debian_branch)

    repo.git.merge(branch)
    print_green("Merged branch '%s' into '%s'" % (branch, debian_branch))

    cd(repo_dir)
    python_version = get_python_version()
    debian_version = debian_version_from_python_version(python_version)
    print_green("The new debian version will be: '%s'" % debian_version)

    dch = git_dch("--debian-branch=%s" % debian_branch,
            "--git-author",
            "--ignore-regex=\".*\"",
            "--multimaint-merge",
            "--since=HEAD",
            "--new-version=%s" % debian_version)
    print_green("Successfully ran '%s'" % " ".join(dch.cmd))

    os.system("vim debian/changelog")
    repo.git.add("debian/changelog")

    if mode == "release":
        os.system("vim debian/changelog")
        repo.git.add("debian/changelog")
        repo.git.commit("-s", "-a", "-m", "Bump new upstream version")
        python_tag = python_version
        debian_tag = "debian/" + python_tag
        repo.git.tag(debian_tag)
        repo.git.tag(python_tag, branch)

    for package in packages:
        # python setup.py should run in its directory
        cd(package)
        package_dir = repo_dir + "/" + package
        res = python(package_dir + "/setup.py", "sdist", _out=sys.stdout)
        print res.stdout
        if package != ".":
            cd("../")

    # Add version.py files to repo
    os.system("grep \"__version_vcs\" -r . -l -I | xargs git add -f")

    build_dir = options.build_dir
    if not options.build_dir:
        build_dir = mktemp("-d", "/tmp/devflow-build-XXX").stdout.strip()
        print_green("Created directory '%s' to store the .deb files." %
                     build_dir)

    cd(repo_dir)
    os.system("git-buildpackage --git-export-dir=%s --git-upstream-branch=%s"
              " --git-debian-branch=%s --git-export=INDEX --git-ignore-new -sa"
              % (build_dir, branch, debian_branch))

    if not options.keep_repo:
        print_green("Removing cloned repo '%s'." % repo_dir)
        rm("-r", repo_dir)
    else:
        print_green("Repository dir '%s'" % repo_dir)

    print_green("Completed. Version '%s', build area: '%s'"
                % (debian_version, build_dir))

    if mode == "release":
        TAG_MSG = "Tagged branch %s with tag %s\n"
        print_green(TAG_MSG % (branch, python_tag))
        print_green(TAG_MSG % (debian_branch, debian_tag))

        UPDATE_MSG = "To update repository %s, go to %s, and run the"\
                     " following commands:\n" + "git_push origin %s\n" * 3

        origin_url = repo.remotes['origin'].url
        remote_url = original_repo.remotes['origin'].url

        print_green(UPDATE_MSG % (origin_url, repo_dir, debian_branch,
                    debian_tag, python_tag))
        print_green(UPDATE_MSG % (remote_url, original_repo.working_dir,
                    debian_branch, debian_tag, python_tag))


if __name__ == "__main__":
    sys.exit(main())
