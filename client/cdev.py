#!/usr/bin/env python3

import json
import os
import sys
import urllib.request
import urllib.parse

class CDevException(Exception):
    def __init__(self,code,desc):
        self.code = code
        self.desc = desc
    def __str__(self):
        return "CDev Exception #{0}: {1}".format(self.code,self.desc)

class CacheInstance:
    def __init__(self, host, super_server_port, web_server_port, username, password):
        self.host = host
        self.port = web_server_port
        self.username = username
        self.password = password
        self.ROOTURL = '/csp/sys/cdev/namespaces'

    @property
    def url_prefix(self):
        return "http://{0}:{1}".format(self.host,self.port)

    def get_namespaces(self):
        return self._request(self.ROOTURL)

    def get_namespace(self,name):
        for namespace in self.get_namespaces():
            if namespace['name'] == name:
                return self._request(namespace['id'])

    def get_files(self,namespace):
        return self._request(namespace['files'])

    def get_file(self, file):
        return self._request(file['id'])

    def put_file(self, file):
        return self._request(file['id'], method="PUT", data=file)

    def add_file(self, namespace, filename, filecontent):
        data = { 'name': filename, 'content': filecontent }
        return self._request(namespace['files'], "PUT", data)

    def compile_file(self, file, spec=""):
        command = { 'action': 'compile', 'spec': spec }
        return self._request(file['id'], method="POST", data=command)

    def get_generated_files(self,file):
        return self.request(file['generated'])

    def _request(self, url, method="GET", data=None):
        requestData = bytes(data,"UTF-8") if data else None
        requestHeaders = {'Content-Type':'application/json'} if data else {}
        requestUrl = self.url_prefix + url
        if self.username and self.password:
            requestUrl += "{0}CacheUserName={1}&CachePassword={2}".format('&' if '?' in requestUrl else '?', self.username, self.password)

        request = urllib.request.Request(
            url = requestUrl,
            headers = requestHeaders,
            data = requestData,
            method = method
        )

        response = urllib.request.urlopen(request)
        return json.loads(response.read().decode("UTF-8"))

# if __name__=="__main__":
#     i = CacheInstance("172.16.196.221", "57772", "USER", "_SYSTEM", "SYS")