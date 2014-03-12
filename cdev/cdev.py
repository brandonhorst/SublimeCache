#!/usr/bin/env python3

import base64
import json
import os
import sys
import urllib.error
import urllib.request
import urllib.parse

class CDevException(Exception):
    def __init__(self,code,desc):
        self.code = code
        self.desc = desc
    def __str__(self):
        return "CDev Exception #{0}: {1}".format(self.code,self.desc)

class Namespace:
    def __init__(self, obj):
        self.id = obj['id']
        self.name = obj['name']
        self.files = obj['files']

class File:
    def __init__(self, obj):
        self.id = obj['id']
        self.name = obj['name']
        if 'content' in obj: self.content = obj['content']
        if 'generatedfiles' in obj: self.generatedfiles = obj['generatedfiles']
        if 'url' in obj: self.url = obj['url']

class FileOperation:
    def __init__(self, obj):
        self.success = obj['success']
        if 'errors' in obj: self.errors = obj['errors']
        if 'file' in obj: self.file = File(obj['file'])

class CacheInstance:
    def __init__(self, host, web_server_port, username, password):
        self.host = host
        self.port = web_server_port
        self.username = username
        self.password = password
        self.ROOTURL = '/csp/sys/dev/namespaces'

    @property
    def url_prefix(self):
        return "http://{0}:{1}".format(self.host,self.port)

    def get_namespaces(self):
        """
        returns:
            [ Namespace ]
        """
        namespaces = self._request(self.ROOTURL)
        return [Namespace(namespace) for namespace in namespaces]

    # def get_namespace(self,name):
    #     """
    #     accepts:
    #         name: str #Numan-readable name. All caps.
    #     returns: Namespace
    #         {
    #             id:    #Namespace URL
    #             name:  #Human-readable name. All caps.
    #             files: #URL to download files

    #         }
    #     """
    #     for namespace in self.get_namespaces():
    #         if namespace.name == name:
    #             return self._request(namespace['id'])

    def get_files(self,namespace):
        """ returns: [ File ] 'content' key not included """
        files = self._request(namespace.files)
        return [File(file) for file in files]

    def get_file(self, file):
        """ accepts: File 'content' key not required
            returns: File """
        result = self._request(file.id)
        return File(result)


    def put_file(self, file):
        """ accepts: File """
        result = self._request(file.id, method="PUT", data=file)
        return FileOperation(result)

    def add_file(self, namespace, filename, filecontent):
        """ accepts:
                namespace:   Namespace
                filename:    str # file name with lowercase extension
                filecontent: str # content (UDL or Routine). Line endings will be automatically converted to \r\n. Class name must match filename.
            returns: File """
        data = { 'name': filename, 'content': filecontent }
        result = self._request(namespace.files, "PUT", data)
        return FileOperation(result)

    def compile_file(self, file, spec=""):
        """ accepts:
                file: File
                spec: %SYSTEM.OBJ flags and compilers. Defaults are defined by the server.
            returns: FileOperation """
        command = { 'action': 'compile', 'spec': spec }
        result = self._request(file.id, method="POST", data=command)
        return FileOperation(result)

    def get_generated_files(self,file):
        """ accepts: File
            returns: [ File ] 'content' key not included """
        if hasattr(file, 'generatedfiles'):
            files = self._request(file.generatedfiles)
            return [File(file) for file in files]
        else:
            return []


    def _request(self, url, method="GET", data=None):
        if data and hasattr(data,'__dict__'):
            data = data.__dict__
        requestData = json.dumps(data).encode() if data else None
        requestHeaders = {'Content-Type':'application/json'} if data else {}
        requestUrl = self.url_prefix + url

        if self.username and self.password:
            base64string = base64.b64encode('{0}:{1}'.format(self.username, self.password).encode()).decode()
            requestHeaders["Authorization"] = 'Basic {0}'.format(base64string)

        request = urllib.request.Request(
            url = requestUrl,
            headers = requestHeaders,
            data = requestData,
            method = method
        )
        
        try:
            response = urllib.request.urlopen(request)
        except urllib.error.URLError as e:
            print("Error Response: {0}".format(e.read()))
            return None
        result = response.read().decode()
        return json.loads(result)

# if __name__=="__main__":
#     i = CacheInstance("172.16.196.221", "57772", "USER", "_SYSTEM", "SYS")