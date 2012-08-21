emir-serp
=========

EMI Registry - Service Endpoint Record Publisher

##Building instructions

###Debian

In case of Debian building you need the source of the code and the __devscripts__ package as building dependency.

For package generation just execute `make -f ./packaging/Debian/Makefile deb` inside the software source directory.
The package and related files are going to be generated into the parent directory.

###Scientific Linux

In case of Scientific Linux building (any SL5 or SL6) you need the source of the code and the __git__ package as building dependency.

Prepare a directory as target for the packages (for example: `mkdir ./RPMS`)
For package generation just execute `rpmbuild -ba --clean --define "_rpmdir ./RPMS" --define "_srcrpmdir ./RPMS" packaging/RedHat/emir-serp.spec;`
inside the software source directroy, where in the command "./RPMS" have to be replaced with the target directory.