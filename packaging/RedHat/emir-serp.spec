#
# Spec file for the EMIR-SERP - EMI Registry - Service Endpoint Record Publisher
#
Summary: EMIR-SERP - EMI Registry - Service Endpoint Record Publisher
Name: emir-serp
Version: 1.2.2
Release: 0%{?dist}
License: CC-BY-SA
Group: Infrastructure Services
URL: https://github.com/eu-emi/emiregistry
BuildArch: noarch
Packager: EMI emir@niif.hu
BuildRequires: git
Requires: python >= 2.4.3, python-simplejson, python-ldap
BuildRoot: %{_tmppath}/%{name}-%{version}
Obsoletes: emird

%description
The EMIR-SERP is a daemon like service that can be executed next to the EMI
services (preferably on the same machine) that are unable to register
themselves into to EMIR Infrastructure
It behaves as an ordinary client ( uses exactly the same, standard
RESTful API as the other clients would do) when perform the automatically
and periodical registration and update against the configured EMI
Registry service instead of the services or other manual administration
tools.

This package contains the EMI Registry - Service Endpoint Record Publisher.

%changelog
* Thu Dec 6 2012 Ivan Marton <martoni@niif.hu>
- Upstream package update - Making emir-serp more robustful by preventing exit while invalid registrations

* Wed Nov 14 2012 Ivan Marton <martoni@niif.hu>
- Upstream package update - restoring python 2.4 support

* Mon Oct 29 2012 Ivan Marton <martoni@niif.hu>
- Adding local BDII LDAP support
- Fixing release and packaging issues

* Wed Oct 24 2012 Ivan Marton <martoni@niif.hu>
- Fixing lintian errors like directory permissions and subsys usage

* Thu Sep 1 2012 Ivan Marton <martoni@niif.hu>
- New mainstream version came out
- Adding logrotate feature and support
- Debian support
- Simplified and more easy-to-use configuration with better default values
- Improved robustness in case of configuration or server side errors
- Improved error reporting and error proxy

* Thu Jul 18 2012 Ivan Marton <martoni@niif.hu>
- Adding former package "emird" as obsoleted package to the specification
- Adding logrotate feature to the package

* Thu Jul 3 2012 Ivan Marton <martoni@niif.hu>
- Renaming product to emir-serp to provide a less misleading name instead of emird.

* Thu Mar 1 2012 Ivan Marton <martoni@niif.hu>
- Fixing rights on the library directory. The previous version of the rpm package was buggy.

* Thu Dec 8 2011 Ivan Marton <martoni@niif.hu>
- Adapting the spec file to ETICS building system and eliminating git dependency

* Thu Dec 1 2011 Ivan Marton <martoni@niif.hu>
- Initial RPM package

%prep
rm -rf %{name}-%{version}
git clone https://github.com/eu-emi/emir-serp.git %{buildroot}/emir-serp/
cd %{buildroot}/emir-serp/
git checkout v1.2.1
cd -
install -d %{buildroot}%{_libdir}/emi/emir-serp/
install -d %{buildroot}%{_sysconfdir}/emi/emir-serp/
install -d %{buildroot}%{_bindir}
install -d %{buildroot}%{_localstatedir}/run/emi/emir-serp/
install -d %{buildroot}%{_defaultdocdir}/%{name}-%{version}
install -d %{buildroot}/var/log/emi/emir-serp
install -d %{buildroot}/etc/init.d
install -d %{buildroot}/etc/logrotate.d
install -m 0644 %{buildroot}/emir-serp/daemon.py %{buildroot}%{_libdir}/emi/emir-serp/
install -m 0644 %{buildroot}/emir-serp/EMIR.py %{buildroot}%{_libdir}/emi/emir-serp/
install -m 0644 %{buildroot}/emir-serp/emir-serp.ini %{buildroot}%{_sysconfdir}/emi/emir-serp/
install -m 0644 %{buildroot}/emir-serp/docs/README %{buildroot}%{_defaultdocdir}/%{name}-%{version}/
install -m 0644 %{buildroot}/emir-serp/docs/example.json %{buildroot}%{_defaultdocdir}/%{name}-%{version}/
install -m 0755 %{buildroot}/emir-serp/emir-serp %{buildroot}%{_bindir}/
install -m 0755 %{buildroot}/emir-serp/packaging/RedHat/initscript/emir-serp %{buildroot}/etc/init.d/
install -m 0644 %{buildroot}/emir-serp/packaging/RedHat/logrotate/emir-serp %{buildroot}/etc/logrotate.d/
rm -rf %{buildroot}/emir-serp


%files
%defattr(755, emi, emi, -)
#
# Config files
#
%dir %attr(755 emi emi) "%{_sysconfdir}/emi/emir-serp"
%config(noreplace) %attr(0644 emi emi) "%{_sysconfdir}/emi/emir-serp/emir-serp.ini"
#
# Log files
#
%dir %attr(0755 emi emi) "/var/log/emi/emir-serp"
#
# Lib files
#
%attr(755 root root) %dir "%{_libdir}/emi/emir-serp"
%attr(644 root root) "%{_libdir}/emi/emir-serp/*.py"
#
# Documentation
#
%doc %{_defaultdocdir}/%{name}-%{version}/README
%doc %{_defaultdocdir}/%{name}-%{version}/example.json
#
# Executable
#
%attr(0755 emi emi) "%{_bindir}/emir-serp"
#
# Lock files
#
%dir %attr(0755 emi emi) "%{_localstatedir}/run/emi/emir-serp"
#
# Init script
#
%attr(0755 emi emi) "/etc/init.d/emir-serp"
#
# Logrotate file
#
%attr(0644 emi emi) "/etc/logrotate.d/emir-serp"


%pre
/usr/sbin/groupadd -r emi 2>/dev/null || :
/usr/sbin/useradd -c "EMI" -g emi \
    -s /sbin/nologin -r -d %{_datadir}/emi emi 2>/dev/null || :

%post
if [ -e /sbin/chkconfig ]; then
    /sbin/chkconfig --add emir-serp
elif [ -e /sbin/insserv ]; then
    /sbin/insserv emir-serp
fi

%preun
/etc/init.d/emir-serp status 2>&1 > /dev/null
if [ "$?" = "0" ]; then 
  /etc/init.d/emir-serp stop >/dev/null 2>&1
fi

if [ -e /sbin/chkconfig ]; then
    /sbin/chkconfig --del emir-serp
elif [ -e /sbin/insserv ]; then
    /sbin/insserv -r emir-serp
fi

