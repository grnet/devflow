Working with devflow
====================

The Devflow development process follows the model described here: 
http://nvie.com/posts/a-successful-git-branching-model/

A summary:

 * There are two eternal branches, **master** and **develop**.
 * The **master** branch is always production-ready.
 * New releases are tagged in the **master** branch.
 * All development happens in separate **feature-** branches, branched off **develop**.
 * When a new release is ready (on **develop**), branch **release-X** is produced. All fine-tuning happens there.
 * Branch **release-X** gets merged into **master** eventually, and tagged as **X** (e.g. *0.18*).
 * If a bug is found in **X**, branch **hotfix-X.Y** is created from the **master**, and the bug is fixed in it. The branch is merged back into **master** and tagged as *X.Y*. If it is needed, the fix should be merged (or cherry-picked) in **develop** or other (e.g. new release) branches.
 * All merges happen with the **--no-ff** argument, to keep commits coming from a single branch grouped together.
 * All feature branches are rebased before being merged into **develop**.
 * For every branch **B**, Debian packages are produced from **debian-B**. The **debian** branch corresponds to the current **master**.

Version Files
-------------

Each project that complies with devflow should have 2 files in the root directory:

* version
* devflow.conf

The first is a *version template file* and the second contains instructions on how devflow should genarate the actual version files of the software. This is done in order to support creating snapshot Debian packages with devflow with ascending versions. During the development of version 0.3, the *version template file* will always contain 0.3.  The devflow computed version of a snapshot may be 0.3dev100. After further development, a newer snapshot will have a greater version (e.g. 0.3dev120).

.. NOTE::
   The software should not import or depend on the template version files itself, but the generated version file(s).

A valid example of a *devflow.conf* file is this one: ::

  [packages ]
    [[ gnt-networking ]]
        version_file = "version.m4","docs/version.py"
        version_template = "version_template","docs/version_template"

This tells devflow that it should generate 2 version files, *version.m4* and *docs/version.py* namely, using the template files *version_template*: ::


  m4_define([devflow_version], [%(DEVFLOW_VERSION)s])

and *docs/version_template*: ::

  __version__ = "%(DEVFLOW_VERSION)s"


The first template will produce `version.m4` which is a valid M4 file that can be directly imported by automake and the second will produce `version.py` which is a valid Python module and can be imported by parts of the software that are written in python.

Debian packages
---------------

*devflow* may be used to create Debian packages. For every branch we want to be able to create Debian packages out of, we 'll need to have a suitable **debian-** branch. We don't need to have the software up-to-date in this branch, only the ``debian/`` directory.

The command for creating packages is this one:

``devflow-autopkg [release]``

This command will:

* Fork the whole repository into a temporary one
* Create a tag in the `HEAD` of the upstream branch if this is a release package
* Merge the upstream branch (e.g. *develop*) into the **debian-** one (e.g. *debian-develop*)
* Compute the package's version based on whether this is a release or a snapshot
* Update the ``debian/changelog`` file of the **debian-** branch
* Create a package using ``git-buildpackage``
* Print instructions on how to push the tag and the debian branch changes back into the original repository (if this is a release)

Branches and version files manipulation
---------------------------------------

develop branch
^^^^^^^^^^^^^^

This is where the vast majority of the software development is done. The *version* file  in this branch should contain the version of the forthcoming major release. If version *0.2.2* is out, the develop branch should contain version *0.3*. After a new release is prepared and a new development circle starts, you can change and commit the new development version by using the command below: ::

  devflow-bump-version <upconfig-version>

At any time, we can create a snapshot package out of the latest development commits by using the command: ::

  devflow-autopkg

This will create a Debian package based on the **debian-develop** branch that hosts the Debian packaging files.

release branch
^^^^^^^^^^^^^^

When the new release is ready on the develop branch, a new release branch is created. If the forthcoming release has version *0.3*, then *release-0.3* branch should be created out of the ``HEAD`` of *develop*. In this release branch, no new features are merged. Only bug fixes and minor issues (like documentation updates) are addressed in here. The first thing we should do after branching off *release-0.3* is to update the version files: ::

  devflow-bump-version 0.3rc1

Once the version is ready we may create a stable release candidate (RC) package doing: ::

  devflow-autopkg release

Before the repository forking is performed, the command will check if *debian-release-0.3* branch exists. If it doesn't, it will create one by branching off *debian-develop*.

After the package is created and the changes are pushed back to the original repo, we may continue by preparing *0.3rc2*: ::

  devflow-bump-version 0.3rc2

master branch
^^^^^^^^^^^^^

After the software's release candidates are tested, we may proceed by creating the new release. In order to do this, we first merge the *release-* branch into *master* and *debian-release-* branch into *debian*: ::

  git checkout master
  git merge --no-ff release-0.3

  git checkout debian
  git merge debian-release-0.3

.. NOTE::
   When merging debian branches, no fast forward is needed

After the merges are performed, we may remove the release branches: ::

  git branch -D release-0.3
  git branch -D debian-release-03

we may then bump version *0.3* in the master branch: ::

  git checkout master
  devflow-bump-version 0.3

And create the packages for release 0.3: ::

  devflow-autopkg release

After this, we push back the packaging changes into the original repo, and prepare the develop branches for release 0.4: ::

  git checkout debian-develop
  git merge debian
  git checkout develop
  git merge --no-ff master
  devflow-bump-version 0.4

.. NOTE::
   We don't need to wait for release 0.3 to be out in order to prepare the develop branch for release 0.4. This could be done right after `release-0.3` branch is created. If we have new features that will not reach version 0.3 but should reach version 0.4 and we have them ready before the release of version 0.3, we may merge them into develop after bumping the develop version to 0.4. This may cause conflicts when `master` gets merged back to develop, but since the changes that are made in the `release-` and the `master` branch are rather conservative, the conflicts should be easily resolvable.

hotfix branch
^^^^^^^^^^^^^

If we find a bug in version *0.3* and cannot afford to wait for release *0.4* to get ready, we should prepare the bug fixing version *0.3.1*. This is done by creating the branch **hotfix-0.3.1** out of the *master* and then bumping the version to *0.3.1*: ::

  git checkout master
  git checkout -b hotfix-0.3.1
  devflow-bump-version 0.3.1

When the development of version 0.3.1 is ready, we create the release packages: ::

  devflow-autopkg release

This command will create the branch *debian-hotfix-0.3.1* out of *debian* if it does not exist. If we need to do changes in the *debian* branch for the hotfix version, we may create it ourselves before the creation of the the packages. 

After we push the changes back to the original repository, we may merge the ephemeral branches back and remove them: ::

  git checkout master
  git merge --no-ff hotfix-0.3.1
  git branch -D hotfix-0.3.1
  git checkout debian
  git merge debian-hotfix-0.3.1
  git granch -D debian-hotfix-0.3.1

We need then to propagate the changes to the develop branches: ::

  git checkout develop
  git merge --no-ff master
  git checout debian-develop
  git merge debian

.. NOTE::
  The first merge will create at least one conflict in the version file. The version file in develop was created after changing 0.3 to 0.4 and the one we merge now was created by changing 0.3 to 0.3.1. This can be easily fixed. The develop version after the merge should still be 0.4. The debian merge should not create a conflict in the version file, because we never manually change those files. They only get updated by devflow (when the upstream branch gets merged into the debian branch), when release packages get created. 

