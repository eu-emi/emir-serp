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

def parse_url(url):
   from urlparse import urlparse
   was_ldap = False
   if url.startswith('ldap://'):
     was_ldap = True
     url = url.replace('ldap://', 'http://', 1)
   (scheme, netloc, path, params, query, fragment) = urlparse(url)
   if was_ldap:
     scheme = 'ldap'
   username = ""
   password = ""
   if "@" in netloc:
       username = netloc.rsplit("@", 1)[0]
       if ":" in username:
           username, password = username.split(":", 1)
   hostname = ""
   netloc_ = netloc.split('@')[-1]
   if '[' in netloc_ and ']' in netloc_:
       hostname = netloc_.split(']')[0][1:].lower()
   elif ':' in netloc_:
       hostname = netloc_.split(':')[0].lower()
   elif netloc_ == '':
       hostname = ""
   else:
       hostname = netloc_.lower()
   port = None
   netloc_ = netloc.split('@')[-1].split(']')[-1]
   if ':' in netloc_:
       port = int(netloc_.split(':')[1], 10)
   class Result:
    def __init__(self, **kwds):
      self.__dict__.update(kwds)
   return Result(scheme=scheme,hostname=hostname,port=port,username=username,password=password,path=path,params=params,query=query,fragment=fragment)

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

    # Allow 'cert', 'key', and 'cadir' attributes to be defined in 'common' section
    if self.parser.has_section('common'):
      if self.cert == attributes['cert'][1] and self.parser.get('common','cert'):
        cert = self.parser.get('common','cert')
      if self.key == attributes['key'][1] and self.parser.get('common','key'):
        key = self.parser.get('common','key')
      if self.cadir == attributes['cadir'][1] and self.parser.get('common','cadir'):
        cadir = self.parser.get('common','cadir')

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
    return [x for x in self.parser.sections() if x != 'emir-serp']

  def getServiceEntry(self, name):
    if not name in self.parser.sections():
      raise Exception('Invalid section name: %s' % name)

    # Error if neither URL nor JSON file is given
    if not 'json_file_location' in self.parser.options(name) and not 'json_dir_location' in self.parser.options(name) and not 'resource_bdii_url' in self.parser.options(name):
      logging.getLogger('emir-serp').warning("json_dir_location, json_file_location or resource_bdii_url has to be defined in '%s' section " % name)
      return []

    # If resource BDII LDAP URL is given, use it
    if 'resource_bdii_url' in self.parser.options(name):
      resource_bdii_url = self.parser.get(name,'resource_bdii_url')
      if not resource_bdii_url:
        logging.getLogger('emir-serp').error("'resource_bdii_url' is present but empty in section %s" % name)
      ldap_url = parse_url(resource_bdii_url)
      if ldap_url.scheme != 'ldap':
        logging.getLogger('emir-serp').error("'%s' is not supported scheme in resource_bdii_url (found in section %s)" % (ldap_url.scheme,name))
        return []
      if not ldap_url.hostname:
        logging.getLogger('emir-serp').error("hostname is missing from resource_bdii_url in section %s" % name)
        return []
      if ldap_url.port is None:
        logging.getLogger('emir-serp').info("port didn't found in resource_bdii_url, default '2170' is used (in section %s)" % name)
      if not ldap_url.path or not ldap_url.path[1:]:
        logging.getLogger('emir-serp').info("base didn't found in resource_bdii_url, default 'o=glue' is used (in section %s)" % name)
      host = ldap_url.hostname
      port = '2170'
      if ldap_url.port:
        port = str(ldap_url.port)
      base = 'o=glue'
      if ldap_url.path and ldap_url.path[1:]:
        base = ldap_url.path[1:]
      filters = '(|(objectClass=GLUE2Service)(objectClass=GLUE2Endpoint))'
      ATTRIBUTES=['GLUE2EntityName', 
            'GLUE2EntityCreationTime',
            'GLUE2EntityValidity',
            'GLUE2ServiceID',
            'GLUE2ServiceType',
            'GLUE2EndpointID',
            'GLUE2EndpointCapability',
            'GLUE2EndpointInterfaceName',
            'GLUE2EndpointInterfaceExtension',
            'GLUE2EndpointQualityLevel',
            'GLUE2EndpointURL',
            'GLUE2EndpointInterfaceVersion',
            'GLUE2EndpointTechnology',
            'GLUE2EndpointServiceForeignKey',
            ]

      logging.getLogger('emir-serp').debug("Retrieving data from %s://%s:%s/%s" % (ldap_url.scheme,host,port,base))
      
      # Connect to LDAP server
      import ldap
      ldap_connection=ldap.initialize(ldap_url.scheme+"://"+host+":"+port)
      try:
        ldap_search_result = ldap_connection.search(
          base,
          ldap.SCOPE_SUBTREE, # this is the default of ldapsearch
          filters,
          ATTRIBUTES
        )
      except ldap.SERVER_DOWN, error_message:
        logging.getLogger('emir-serp').error("Error message from server %s://%s:%s: %s" % (ldap_url.scheme,host,port,error_message[0]['desc']))
        return []

      # Fetch data from LDAP server
      ldap_result_set = []
      while 1:
        try:
          ldap_result_type, ldap_result_data = ldap_connection.result(ldap_search_result, 0)
        except ldap.LDAPError, ex:
          logging.getLogger('emir-serp').error("LDAP Error in section %s: %s" % (name, ex[0]['desc']))
        if (ldap_result_data == []):
          break
        else:
          if ldap_result_type == ldap.RES_SEARCH_ENTRY:
            ldap_result_set.append(ldap_result_data)
      if ldap_result_set == []:
        return []
      
      # Parse and properly merge LDAP results
      mapping = {
        'GLUE2ServiceID': 'Service_ID',
        'GLUE2EntityName': 'Service_Name',
        'GLUE2ServiceType': 'Service_Type',
        'GLUE2EndpointID': 'Service_Endpoint_ID',
        'GLUE2EndpointURL': 'Service_Endpoint_URL',
        'GLUE2EndpointCapability': 'Service_Endpoint_Capability',
        'GLUE2EndpointInterfaceName': 'Service_Endpoint_InterfaceName',
        'GLUE2EndpointInterfaceVersion': 'Service_Endpoint_InterfaceVersion',
        'GLUE2EndpointTechnology': 'Service_Endpoint_Technology',
        'GLUE2EndpointQualityLevel': 'Service_Endpoint_QualityLevel',
        'GLUE2EntityCreationTime': 'Service_CreationTime',
        'GLUE2ServiceAdminDomainForeignKey': 'Service_Admin_Domain',
        'GLUE2EndpointImplementationName': 'Service_Endpoint_Implementation_Name',
        'GLUE2EndpointImplementationVersion': 'Service_Endpoint_Implementation_Version',
      } 

      services = {}
      endpoints = []
      result = []

      for entry in ldap_result_set:
        ldap_id, value = entry[0]
        if ldap_id.startswith("GLUE2ServiceID"):
          services[value["GLUE2ServiceID"][0]] = value
        if ldap_id.startswith("GLUE2EndpointID"):
          endpoints.append(value)

      for endpoint in endpoints:
        endpoint.update(services[endpoint["GLUE2EndpointServiceForeignKey"][0]])
        new_endpoint = {}
        for key, value in endpoint.items():
          if key in mapping.keys() and key not in ['GLUE2EndpointServiceForeignKey']:
            if key in ['GLUE2EndpointCapability']:
              new_endpoint[mapping[key]]=value
            else:
              new_endpoint[mapping[key]]=value[0]
        result.append(new_endpoint)
      return result 

    # If JSON watch dir is given, use it
    if 'json_dir_location' in self.parser.options(name):
      json_dir = self.parser.get(name,'json_dir_location')
      try:
        filelist = listdir(json_dir)
      except:
        logging.getLogger('emir-serp').error("'%s' is not a directory" % json_dir)
        return []
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
        logging.getLogger('emir-serp').error("No files with proper json document has been found in the '%s' directory" % json_dir)
        return []
      return json_list

    # If JSON file is given use it
    if 'json_file_location' in self.parser.options(name):
      json_file = self.parser.get(name,'json_file_location')
      if not exists(json_file):
        logging.getLogger('emir-serp').error("JSON file cannot be found on path: %s" % json_file)
        return []
      if not access(json_file, R_OK):
        logging.getLogger('emir-serp').error("JSON file cannot be read on path: %s" % json_file)
        return []
      fp = open(json_file)
      jsondoc = ''
      try:
        jsondoc = json.load(fp)
      except ValueError:
        logging.getLogger('emir-serp').error("JSON cannot be converted in file: %s" % json_file)
        return []
      return jsondoc

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
        import pickle

        thefile = open('/tmp/test.txt', 'w')
        pickle.dump(service_entry, thefile)
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
    if self.config.secureUrl:
      proto = 'https'
    else:
      proto = 'http'
    for item in self.compose_registration_update_message():
      if 'Service_Endpoint_ID' in item:
        logging.getLogger('emir-serp').info('REGISTRATION Successful. Check here: %s://%s:%s/services?Service_Endpoint_ID=%s' % (proto , self.config.host, self.config.port, item['Service_Endpoint_ID']))
      elif 'Service_Endpoint_URL' in item:
        logging.getLogger('emir-serp').info('REGISTRATION Successful. Check here: %s://%s:%s/services?Service_Endpoint_URL=%s' % (proto , self.config.host, self.config.port, item['Service_Endpoint_URL']))
      else:
        logging.getLogger('emir-serp').info('REGISTRATION Successful. Check here: %s' % item)

  def register(self):
    # Composing and sending registration message
    parameters = json.dumps(self.compose_registration_update_message())
    headers = {"Content-type": "application/json", "Accept": "application/json, text/plain"}
    self.communicate('POST', '/serviceadmin', parameters, headers)
    if self.config.secureUrl:
      proto = 'https'
    else:
      proto = 'http'
    for item in self.compose_registration_update_message():
      if 'Service_Endpoint_ID' in item:
        logging.getLogger('emir-serp').info('REGISTRATION Successful. Check here: %s://%s:%s/services?Service_Endpoint_ID=%s' % (proto , self.config.host, self.config.port, item['Service_Endpoint_ID']))
      elif 'Service_Endpoint_URL' in item:
        logging.getLogger('emir-serp').info('REGISTRATION Successful. Check here: %s://%s:%s/services?Service_Endpoint_URL=%s' % (proto , self.config.host, self.config.port, item['Service_Endpoint_URL']))
      else:
        logging.getLogger('emir-serp').info('REGISTRATION Successful. Check here: %s' % item)

  def delete(self):
    # Composing and sending delete message
    for entry in self.config.getServiceEntries():
      service_entry = self.config.getServiceEntry(entry)
      if not isinstance(service_entry, list):
        service_entry = [service_entry]
      for item in service_entry:
        try:
          self.communicate('DELETE', '/serviceadmin?Service_Endpoint_ID='+item['Service_Endpoint_ID'])
        except Exception, ex:
          logging.getLogger('emir-serp').error('Error during deletion: %s' % ex)

