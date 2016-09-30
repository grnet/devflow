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

"""Helper script for automatic build of Debian packages."""

import os
import sys
import subprocess

from git import GitCommandError
from optparse import OptionParser
from sh import mktemp, cd, rm  # pylint: disable=E0611
from functools import partial
try:
    from sh import git_dch as gbp_dch  # pylint: disable=E0611
    gbp_buildpackage = ['git-buildpackage']
except ImportError:
    # In newer versions of git-buildpackage the executables have changed.
    # Instead of having various git-* executables, there is only a gbp one,
    # which expects the command (dch, buildpackage, etc) as the first argument.
    from sh import gbp  # pylint: disable=E0611
    gbp_dch = partial(gbp, 'dch')
    gbp_buildpackage = ['gbp', 'buildpackage']

from devflow import versioning
from devflow import utils
from devflow import BRANCH_TYPES


AVAILABLE_MODES = ["release", "snapshot"]

DESCRIPTION = """Tool for automatic build of Debian packages.

%(prog)s is a helper script for automatic build of Debian packages from
repositories that follow the `git flow` development model
<http://nvie.com/posts/a-successful-git-branching-model/>.

This script must run from inside a clean git repository and will perform the
following steps:
    * Clone your repository to a temporary directory
    * Merge the current branch with the corresponding debian branch
    * Compute the version of the new package and update the python
      version files
    * Create a new entry in debian/changelog, using `git-dch`
    * Create the Debian packages, using `git-buildpackage`
    * Tag the appropriate branches if in `release` mode

%(prog)s will work with the packages that are declared in `devflow.conf'
file, which must exist in the top-level directory of the git repository.

"""


def print_help(prog):
    print DESCRIPTION % {"prog": prog}


def main():
    from devflow.version import __version__  # pylint: disable=E0611,F0401
    parser = OptionParser(usage="usage: %prog [options] mode",
                          version="devflow %s" % __version__,
                          add_help_option=False)
    parser.add_option("-h", "--help",
                      action="store_true",
                      default=False,
                      help="show this help message")
    parser.add_option("-k", "--keep-repo",
                      action="store_true",
                      dest="keep_repo",
                      default=False,
                      help="Do not delete the cloned repository")
    parser.add_option("-b", "--build-dir",
                      dest="build_dir",
                      default=None,
                      help="Directory to store created packages")
    parser.add_option("-r", "--repo-dir",
                      dest="repo_dir",
                      default=None,
                      help="Directory to clone repository")
    parser.add_option("-d", "--dirty",
                      dest="force_dirty",
                      default=False,
                      action="store_true",
                      help="Do not check if working directory is dirty")
    parser.add_option("-c", "--config-file",
                      dest="config_file",
                      help="Override default configuration file")
    parser.add_option("--no-sign",
                      dest="sign",
                      action="store_false",
                      default=True,
                      help="Do not sign the packages")
    parser.add_option("--key-id",
                      dest="keyid",
                      help="Use this keyid for gpg signing")
    parser.add_option("--dist",
                      dest="dist",
                      default=None,
                      help="Force distribution in Debian changelog")
    parser.add_option("-S", "--source-only",
                      dest="source_only",
                      default=False,
                      action="store_true",
                      help="Specifies a source-only build, no binary packages"
                           " need to be made.")
    parser.add_option("--debian-branch",
                      dest="debian_branch",
                      default=None,
                      help="Use this debian branch, instead of"
                           "auto-discovering the debian branch to use")
    parser.add_option("--push-back",
                      dest="push_back",
                      default=False,
                      action="store_true",
                      help="Automatically push branches and tags to repo.")
    parser.add_option("--color",
                      dest="color_output",
                      default="auto",
                      help="Enable/disable colored output. Default mode is"
                           " auto, available options are yes/no")

    (options, args) = parser.parse_args()

    if options.color_output == "yes":
        use_colors = True
    elif options.color_output == "no":
        use_colors = False
    else:
        use_colors = sys.stdout.isatty()

    red = lambda x: x
    green = lambda x: x

    if use_colors:
        try:
            import colors
            red = colors.red
            green = colors.green
        except AttributeError:
            pass

    print_red = lambda x: sys.stdout.write(red(x) + "\n")
    print_green = lambda x: sys.stdout.write(green(x) + "\n")

    if options.help:
        print_help(parser.get_prog_name())
        parser.print_help()
        return

    # Get build mode
    try:
        mode = args[0]
    except IndexError:
        mode = utils.get_build_mode()
    if mode not in AVAILABLE_MODES:
        raise ValueError(red("Invalid argument! Mode must be one: %s" %
                             ", ".join(AVAILABLE_MODES)))

    # Load the repository
    original_repo = utils.get_repository()

    # Check that repository is clean
    toplevel = original_repo.working_dir
    if original_repo.is_dirty() and not options.force_dirty:
        raise RuntimeError(red("Repository %s is dirty." % toplevel))

    # Get packages from configuration file
    config = utils.get_config(options.config_file)
    packages = config['packages'].keys()
    print_green("Will build the following packages:\n" + "\n".join(packages))

    # Get current branch name and type and check if it is a valid one
    branch = original_repo.head.reference.name
    branch = utils.undebianize(branch)
    branch_type_str = utils.get_branch_type(branch)

    if branch_type_str not in BRANCH_TYPES.keys():
        allowed_branches = ", ".join(BRANCH_TYPES.keys())
        raise ValueError("Malformed branch name '%s', cannot classify as"
                         " one of %s" % (branch, allowed_branches))

    # Fix needed environment variables
    v = utils.get_vcs_info()
    os.environ["DEVFLOW_BUILD_MODE"] = mode
    os.environ["DEBFULLNAME"] = v.name
    os.environ["DEBEMAIL"] = v.email

    # Check that base version file and branch are correct
    versioning.get_python_version()

    # Get the debian branch
    if options.debian_branch:
        debian_branch = options.debian_branch
    else:
        debian_branch = utils.get_debian_branch(branch)
    origin_debian = "origin/" + debian_branch

    # Clone the repo
    repo_dir = options.repo_dir or create_temp_directory("df-repo")
    repo_dir = os.path.abspath(repo_dir)
    repo = original_repo.clone(repo_dir, branch=branch)
    print_green("Cloned repository to '%s'." % repo_dir)

    build_dir = options.build_dir or create_temp_directory("df-build")
    build_dir = os.path.abspath(build_dir)
    print_green("Build directory: '%s'" % build_dir)

    # Create the debian branch
    repo.git.branch(debian_branch, origin_debian)
    print_green("Created branch '%s' to track '%s'" %
                (debian_branch, origin_debian))

    # Go to debian branch
    repo.git.checkout(debian_branch)
    print_green("Changed to branch '%s'" % debian_branch)

    # Merge with starting branch
    repo.git.merge(branch)
    print_green("Merged branch '%s' into '%s'" % (branch, debian_branch))

    # Compute python and debian version
    cd(repo_dir)
    python_version = versioning.get_python_version()
    debian_version = versioning.\
        debian_version_from_python_version(python_version)
    print_green("The new debian version will be: '%s'" % debian_version)

    # Update the version files
    versioning.update_version()

    if not options.sign:
        sign_tag_opt = None
    elif options.keyid:
        sign_tag_opt = "-u=%s" % options.keyid
    elif mode == "release":
        sign_tag_opt = "-s"
    else:
        sign_tag_opt = None

    # Tag branch with python version
    branch_tag = python_version
    tag_message = "%s version %s" % (mode.capitalize(), python_version)
    try:
        repo.git.tag(branch_tag, branch, sign_tag_opt, "-m %s" % tag_message)
    except GitCommandError:
        # Tag may already exist, if only the debian branch has changed
        pass
    upstream_tag = "upstream/" + branch_tag
    repo.git.tag(upstream_tag, branch)

    # Update changelog
    dch = gbp_dch("--debian-branch=%s" % debian_branch,
                  "--git-author",
                  "--ignore-regex=\".*\"",
                  "--multimaint-merge",
                  "--since=HEAD",
                  "--new-version=%s" % debian_version)
    print_green("Successfully ran '%s'" % " ".join(dch.cmd))

    if options.dist is not None:
        distribution = options.dist
    elif mode == "release":
        distribution = utils.get_distribution_codename()
    else:
        distribution = "unstable"

    f = open("debian/changelog", 'r+')
    lines = f.readlines()
    lines[0] = lines[0].replace("UNRELEASED", distribution)
    lines[2] = lines[2].replace("UNRELEASED", "%s build" % mode)
    f.seek(0)
    f.writelines(lines)
    f.close()

    if mode == "release":
        subprocess.check_call(['editor', "debian/changelog"])

    # Add changelog to INDEX
    repo.git.add("debian/changelog")
    # Commit Changes
    repo.git.commit("-s", "debian/changelog",
                    m="Bump version to %s" % debian_version)
    # Tag debian branch
    debian_branch_tag = "debian/" + utils.version_to_tag(debian_version)
    tag_message = "%s version %s" % (mode.capitalize(), debian_version)
    if mode == "release":
        repo.git.tag(debian_branch_tag, sign_tag_opt, "-m %s" % tag_message)

    # Create debian packages
    cd(repo_dir)
    version_files = []
    for _, pkg_info in config['packages'].items():
        if pkg_info.get("version_file"):
            version_files.extend(pkg_info.as_list('version_file'))

    # Add version.py files to repo
    repo.git.add("-f", *version_files)

    # Export version info to debuilg environment
    os.environ["DEB_DEVFLOW_DEBIAN_VERSION"] = debian_version
    os.environ["DEB_DEVFLOW_VERSION"] = python_version

    args = list(gbp_buildpackage)
    args.extend(["--git-export-dir=%s" % build_dir,
                 "--git-upstream-branch=%s" % branch,
                 "--git-debian-branch=%s" % debian_branch,
                 "--git-export=INDEX",
                 "--git-ignore-new",
                 "-sa",
                 "--source-option=--auto-commit",
                 "--git-upstream-tag=%s" % upstream_tag])

    if options.source_only:
        args.append("-S")
    if not options.sign:
        args.extend(["-uc", "-us"])
    elif options.keyid:
        args.append("-k\"'%s'\"" % options.keyid)

    subprocess.check_call(args)

    # Remove cloned repo
    if mode != 'release' and not options.keep_repo:
        print_green("Removing cloned repo '%s'." % repo_dir)
        rm("-r", repo_dir)

    # Print final info
    info = (("Version", debian_version),
            ("Upstream branch", branch),
            ("Upstream tag", branch_tag),
            ("Debian branch", debian_branch),
            ("Debian tag", debian_branch_tag),
            ("Repository directory", repo_dir),
            ("Packages directory", build_dir))
    print_green("\n".join(["%s: %s" % (name, val) for name, val in info]))

    # Print help message
    if mode == "release":
        origin = original_repo.remote().url
        repo.create_remote("original_origin", origin)
        print_green("Created remote 'original_origin' for the repository '%s'"
                    % origin)

        print_green("To update repositories '%s' and '%s' go to '%s' and run:"
                    % (toplevel, origin, repo_dir))
        for remote in ['origin', 'original_origin']:
            objects = [debian_branch, branch_tag, debian_branch_tag]
            print_green("git push %s %s" % (remote, " ".join(objects)))
        if options.push_back:
            objects = [debian_branch, branch_tag, debian_branch_tag]
            repo.git.push("origin", *objects)
            print_green("Automatically updated origin repo.")


def create_temp_directory(suffix):
    create_dir_cmd = mktemp("-d", "/tmp/" + suffix + "-XXXXX")
    return create_dir_cmd.stdout.strip()


if __name__ == "__main__":
    sys.exit(main())
