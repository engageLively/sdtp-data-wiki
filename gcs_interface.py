from google.cloud import storage
import json
from sdtp import InvalidDataException


class SDMLStorageBucket:
  '''
  An object which is the interface to the Google Cloud Storage Bucket holding SDML files 
  as blobs.  The SDML files should all end with '.sdml' and be valid tables
  '''
  def __init__(self, bucket_name):
    self.bucket_name = bucket_name
    self.client = storage.Client()
    self.bucket = self.client.bucket(bucket_name)

  def get_all_table_names(self, prefix = None):
    '''
    Get the names of all tables stored in the bucket.  Returns a list of blob names
    '''
    blobs = self.client.list_blobs(self.bucket)
    names = [blob.name for blob in blobs]
    names = [name for name in names if name.endswith('.sdml')]
    if prefix is not None:
      names = [name for name in names if name.startswith(prefix)]
    return names
  
  def _get_json_blob(self, blob_name):
    # A utility to get blob blob_name, whioch is a json file
    # and return it as the Python object.  Worker for get_
    try:
      blob = self.bucket.blob(blob_name)
      json_form = blob.download_as_string()
      result  = json.loads(json_form)
      return result
    except Exception as e:
      raise InvalidDataException(f'Error {repr(e)} reading  {blob_name}')
  
  def get_table_as_dictionary(self, table_name):
    '''
    Get table table_name as the dictionary form.  The SDML blob in the bucket should be 
    an SDML file in JSON form
    Arguments: 
      table_name: the name of the table to get
    Returns:
      The table as a JSON dictionary
    '''
    return self._get_json_blob(table_name)
  
  def upload_table(self, prefix, table_dictionary):
    '''
    Upload a table to the bucket, to blob name table_name.  table should be an SDMLTable with 
    a .to_dictionary() method that produces a JSONifiable form
    Arguments:
      table_name: name of the table
      table: the SDML Table; note this is an instance of SDMLTable, not a dictionary
    
    '''
    table_name = table_dictionary["name"]

    blob = self.bucket.blob(f'{prefix}/{table_name}.sdml')
    json_form = json.dumps(table_dictionary['table'])
    blob.upload_from_string(json_form, content_type = 'application/json')

  def get_sdql_samples(self):
      '''
      Get the sample SDQL queries, which are stored in 'samples/table_sample_queries.json'
      '''
      try:
        return self._get_json_blob('gcstables/samples/table_sample_queries.json')
      except InvalidDataException:
        return {}


