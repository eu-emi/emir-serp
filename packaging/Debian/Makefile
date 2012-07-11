DEBENV = packaging/Debian
VERSION = $(shell cat $(DEBENV)/VERSION)
EXCLUDES = --exclude=.git
FILES = EMIR.py daemon.py  docs  emir-serp  emir-serp.ini

default:
	echo "You didn't really want to do this..."

deb:
	rm -rf .git .gitignore
	cp -a $(DEBENV)/debian .
	tar -cvzf ../emir-serp_$(VERSION).orig.tar.gz \
		$(EXCLUDES) $(FILES)
	debuild -us -uc

clean:
	rm -rf debian

