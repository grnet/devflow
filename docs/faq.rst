Frequently asked questions (FAQ)
================================

Should the generated version files be added into the repository?
----------------------------------------------------------------

This depends on whether you want devflow be a hard or a soft dependency in your project.devflow will generate version files (using the template version file) whenever a package is generated. If you plan to install your software only using debian packages, this should be enough, but keep in mind that the code hosted in the repository is crippled. You will always need to execute: ``devflow-update-version`` to create the missing files. A python project may expect to import the version module which by default is not present. SCM frameworks like github automatically create source archives for each git tag. If a user downloads this archive, he'll expect it to be complete.

A better approach is to have the generated files in the repository and let devflow overwrite them whenever necessary. A good practice would be to update the generated version files whenever a ``devflow-bump-version`` is executed. If we bump the development version *0.3* we could save *0.3dev0* to the generated version files. We could even make ``devflow-bump-version`` do this automatically if the generated version files are present. We recommend the **dev0** postfix because devflow-generated snapshots will have versions postfixed with *devX*, where *X* is always greater that *0*. Whenever there is a  software installed on a system and has a version that is postfixed with **dev0**, the user will know that this is a snapshot version that was installed manually, using the software's build system, without devflow. Also, whenever we want to make a new release, we first do: ::

  env DEVFLOW_BUILDMODE=release devflow-update-version

and commit the updated auto-generated version files before tagging. The command above creates versions without the *devX* postfix, which indicates that this is a release.

Can I generate Debian packages for different releases?
------------------------------------------------------

The answer is yes. The *debian-* branches are optionally postfixed with the code name of the Debian or Ubuntu release. If we are building a package from a commit on the *develop* branch on an Ubuntu 16.04 system, devflow will favor the use of **debian-develop-xenial** and will fall back to **debian-develop** only if the aforementioned branch is not locally available.

That does not mean that you need to have *debian-*-xenial* branches for every available non-Debian branch. Most of the time we develop and try the software in only one OS. When the software is ready, we release it and then create packages for every supported OS. In this case, we only need to have one *debian-develop* branch  and many *debian-<codename>* branches.

