#Verification and attribute derivation
import re
# Logging facility
import logging
# JSON encoding - fallback to json if simplejson is not present
try: import simplejson as json
except ImportError: import json
# File checking
from os.path import exists, join
from os import listdir, access, R_OK
# INI style configuration parsing
from ConfigParser import SafeConfigParser

class EMIRConfiguration:

  def __init__(self, config_file):
    if not exists(config_file):
      raise Exception("Configuration file cannot be found on path: %s" % config_file)
    self.parser = SafeConfigParser()
    self.parser.read(config_file)

    # Define common attributes. Format: 'name': (Mandatory, 'default value', 'verification regexp')
    attributes = {
      'verbosity': (False, 'error', ''),
      'url': (True, '', ''),
      'period': (True, '', ''),
      'validity': (True, '', ''),
      'cert': (False, '/etc/grid-security/hostcert.pem', ''),
      'key': (False, '/etc/grid-security/hostkey.pem', ''),
      'cadir': (False, '/etc/grid-security/certificates', ''),
    }
    # Parse common configuration options and fill default values if necessary
    if not self.parser.has_section('emir-serp'):
      raise Exception("Section 'emir' is missing from the configuration file")
    for attr in [x for x in attributes.keys() if attributes[x][0]]:
      if not attr in self.parser.options('emir-serp'):
        raise Exception("The '%s' item cannot be found in '%s' section" % (attr, 'emir-serp'))
      setattr(self,attr,self.parser.get('emir-serp',attr))

    for attr in [x for x in attributes.keys() if not attributes[x][0]]:
      if attr in self.parser.options('emir-serp'):
        setattr(self,attr,self.parser.get('emir-serp',attr))
      else:
        setattr(self,attr,attributes[attr][1])

    # Verification 
    # TODO: verification pattern and logic here

    # Extract derived attributes from the original ones from ini config
    url_derivator = re.compile("^(http[s]?://)?([^:/]+)(:(\d*))?$")
    m = url_derivator.match(self.url)
    if not m:
      raise Exception('Invalid URL format in url attribute')

    if m.group(1) == 'http://':
      self.secureUrl = False
      self.protocol = 'http'
    else:
      self.secureUrl = True
      self.protocol = 'https'

    self.host = m.group(2)

    if m.group(4):
      self.port = int(m.group(4))
    else:
      self.port = 54321

    self.validity = int(self.validity)
    self.period = float(self.period)

    # Mapping verbosity string to integer level
    default_verbosity = attributes['verbosity'][1]
    verbosity_map = {
      'error': logging.ERROR,
      'info':  logging.INFO,
      'debug': logging.DEBUG,
    }

    if not self.verbosity in verbosity_map.keys():
      logging.getLogger('emir-serp').error("Configuration error. '%s' is an invalid value for verbosity configuration option '%s' used instead" % (self.verbosity, default_verbosity))
      self.verbosity = default_verbosity

    self.loglevel = verbosity_map[self.verbosity]

    # Checking key and certificate file if necessary
    if self.secureUrl:
      if not exists(self.key):
        raise Exception("Configuration error: key file cannot be found on path: %s" % self.key)
      if not access(self.key, R_OK):
        raise Exception("Key file cannot be read on path: %s" % self.key)
      if not exists(self.cert):
        raise Exception("Configuration error: certificate file cannot be found on path: %s" % self.cert)
      if not access(self.cert, R_OK):
        raise Exception("Cert file cannot be read on path: %s" % self.cert)
    
  def getServiceEntries(self):
    return [x for x in self.parser.sections() if x != 'emir']

  def getServiceEntry(self, name):
    if not name in self.parser.sections():
      raise Exception('Invalid section name: %s' % name)

    # Error if neither URL nor JSON file is given
    if not 'json_file_location' in self.parser.options(name) and not 'json_dir_location' in self.parser.options(name):
      logging.getLogger('emir-serp').warning("json_dir_location or json_file_location has to be defined in '%s' section " % name)
      return []

    # If JSON file is given use it
    if 'json_file_location' in self.parser.options(name) and not 'json_dir_location' in self.parser.options(name):
      json_file = self.parser.get(name,'json_file_location')
      if not exists(json_file):
        raise Exception("JSON file cannot be found on path: %s" % json_file)
      if not access(json_file, R_OK):
        raise Exception("JSON file cannot be read on path: %s" % json_file)
      fp = open(json_file)
      jsondoc = ''
      try:
        jsondoc = json.load(fp)
      except ValueError:
        raise Exception("JSON object problem in file: %s" % json_file)
      return jsondoc

    if 'json_dir_location' in self.parser.options(name):
      json_dir = self.parser.get(name,'json_dir_location')
      try:
        filelist = listdir(json_dir)
      except:
        raise Exception("Dir '%s' is not a directory" % json_dir)
      json_list = []
      for json_file in filelist:
        jsondoc = []
        try:
          fp = open(join(json_dir,json_file))
          jsondoc = json.load(fp)
        except:
          pass
        if not isinstance(jsondoc, list):
          json_list.append(jsondoc)
        else:
          json_list.extend(jsondoc)
          if not json_list:
            raise Exception("No proper json document has been found in the '%s' directory" % json_dir)
          return json_list

    # If any other issue happens this catch-all return reuturns an empty list
    return []

import urllib, urllib2, httplib
import datetime
class EMIRClient:
  def __init__(self, config):
    self.config = config

  def communicate(self, method, path, parameters=False,  headers=False):
    connection = ''
    if self.config.secureUrl:
      connection = httplib.HTTPSConnection(self.config.host, self.config.port, self.config.key, self.config.cert)
    else:
      connection = httplib.HTTPConnection(self.config.host, self.config.port)
    if parameters:
      if headers:
        connection.request(method, path, parameters, headers)
      else:
        connection.request(method, path, parameters)
    else:
      connection.request(method, path)
    response = connection.getresponse()
    server_response = response.read()
    connection.close()
    if response.status != 200:
      raise Exception("%s (%s): %s" % (response.reason, response.status, server_response))
    return server_response
    
  def ping(self):
    ping_response = self.communicate('GET', '/ping')
    return json.loads(ping_response)['RunningSince']

  def compose_registration_update_message(self):
    service_entries = []
    for entry in self.config.getServiceEntries():
      try:
        service_entry = self.config.getServiceEntry(entry)
        if not isinstance(service_entry, list):
          service_entry = [service_entry]
        # Service creation time and expire on timestamp hacking because the too strict
        # java requirements that aren't really following the iso standards.
        # Instead of these:
        # service_entry['Service_CreationTime']={
        #   '$date': datetime.datetime.utcnow().isoformat()+'Z'
        # }
        # service_entry['Service_ExpireOn']={
        #   '$date': (datetime.datetime.utcnow()+datetime.timedelta(hours=self.config.validity)).isoformat()+'Z'
        # }
        # Doing these:
        for item in service_entry:
          item['Service_CreationTime'] = {
            '$date': datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
          }
          item['Service_ExpireOn'] = {
            '$date': (datetime.datetime.utcnow()+datetime.timedelta(hours=self.config.validity)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
          }
          # -- End of hack ;-)

          # Check of entry could be placed here

          if 'Service_Endpoint_ID' in item and 'Service_Endpoint_URL' in item:
            logging.getLogger('emir-serp').debug('REGISTRATION: Endpoint ID: %s; URL: %s' % (item['Service_Endpoint_ID'], item['Service_Endpoint_URL']))
          elif 'Service_Endpoint_ID' in item:
            logging.getLogger('emir-serp').debug('REGISTRATION: Endpoint ID: %s' % item['Service_Endpoint_ID'])
          elif 'Service_Endpoint_URL' in item:
            logging.getLogger('emir-serp').debug('REGISTRATION: Endpoint URL: %s' % item['Service_Endpoint_URL'])

          service_entries.append(item)
      except Exception, ex:
        logging.getLogger('emir-serp').error('Message composing error: %s' % ex)
    return service_entries

  def update(self):
    # Composing and sending update message
    parameters = json.dumps(self.compose_registration_update_message())
    headers = {"Content-type": "application/json", "Accept": "application/json, text/plain"}
    self.communicate('PUT', '/serviceadmin', parameters, headers)

  def register(self):
    # Composing and sending registration message
    parameters = json.dumps(self.compose_registration_update_message())
    headers = {"Content-type": "application/json", "Accept": "application/json, text/plain"}
    self.communicate('POST', '/serviceadmin', parameters, headers)

  def delete(self):
    # Composing and sending delete message
    for entry in self.config.getServiceEntries():
      service_entry = self.config.getServiceEntry(entry)
      if not isinstance(service_entry, list):
        service_entry = [service_entry]
      for item in service_entry:
        self.communicate('DELETE', '/serviceadmin?Service_Endpoint_URL='+item['Service_Endpoint_URL'])

