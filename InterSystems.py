import os
import re
import sys
import subprocess
import sublime_plugin
import sublime
import threading

cdevPath = '/Users/brandonhorst/Dropbox/Programming/cdev/client'
if cdevPath not in sys.path:
    sys.path += [cdevPath]
from cdev import CacheInstance

def settings_get(name, default=None):
    plugin_settings = sublime.load_settings('InterSystems.sublime-settings')

    return plugin_settings.get(name,default)

def settings_set(name, value):
    plugin_settings = sublime.load_settings('InterSystems.sublime-settings')
    plugin_settings.set(name, value)
    sublime.save_settings('InterSystemsCache.sublime-settings')

def current_namespace():
    instance_name = settings_get('current-server')
    servers = settings_get('servers',{})
    server = servers.get(instance_name)

    current_namespace_name = server['namespace']
    return current_instance().get_namespace(current_namespace_name)

def current_instance():
    instance_name = settings_get('current-server')
    servers = settings_get('servers',{})
    server = servers.get(instance_name)

    del server['namespace']
    return CacheInstance(**server)

class InsertText(sublime_plugin.TextCommand):
    def run(self,edit,text,isClass,name):
        self.view.erase(edit, sublime.Region(0, self.view.size()))
        self.view.insert(edit,0,text.replace("\r\n","\n"))
        self.view.set_name(name)
        syntaxFile = "UDL" if isClass else "COS"
        self.view.set_syntax_file('Packages/CacheColors/{0}.tmLanguage'.format(syntaxFile))

class DownloadClassOrRoutine(sublime_plugin.ApplicationCommand):
    def download(self,index):
        if index >= 0:
            file = self.files[index]
            content = current_instance().get_file(file)['content']
            view = sublime.active_window().new_file()
            view.run_command('insert_text',{'text':content,'isClass': True, 'name': file['name']})
            view.settings().set('file',file)
    def run(self):
        threading.Thread(target=self.go).start()

    def go(self):
        self.files = current_instance().get_files(current_namespace())
        sublime.active_window().show_quick_panel([file['name'] for file in self.files], self.download)

class UploadClassOrRoutine(sublime_plugin.ApplicationCommand):
    def get_class_name(self):
        match = re.search(r"^Class\s((\w|\.)+)\s", self.text, re.MULTILINE)
        return match.group(1)

    def update(self,newFile):
        self.view.settings().set('file',newFile)
        self.view.run_command('insert_text', {'text': newFile['content'], 'isClass': True, 'name': newFile['name']} )

    def take_name(self, name):
        new_file = current_instance().add_file(current_namespace(), name, self.text)
        self.update(nweFile)

    def run(self):
        threading.Thread(target=self.go).start()

    def go(self):
        self.view = sublime.active_window().active_view()
        self.text = self.view.substr(sublime.Region(0, self.view.size())).replace('\n','\r\n')
        
        file = self.view.settings().get('file')
        if file:
            file['content'] = self.text
            new_file = current_instance().put_file(file)
            self.update(new_file)
        else:
            class_name = self.get_class_name()
            if class_name:
                new_file = current_instance().add_file(current_namespace(), class_name, self.text)
                self.update(newFile)
            else:
                self.view.window().show_input_panel("Enter a name for this routine", "", self.take_name)

class ChangeCacheNamespace(sublime_plugin.ApplicationCommand):
    def change(self, index):
        if index >= 0:
            servers = settings_get('servers',{})
            serverName = settings_get('current-server')
            servers[serverName]['namespace'] = self.namespaces[index]['name']
            settings_set('servers',servers)

    def run(self):
        threading.Thread(target=self.go).start()

    def go(self):
        self.namespaces = current_instance().get_namespaces()
        sublime.active_window().show_quick_panel([namespace['name'] for namespace in self.namespaces], self.change)

class ChangeCacheInstance(sublime_plugin.ApplicationCommand):
    def change(self,index):
        if index >= 0:
            settings_set('current-server',self.items[index])
            
    def run(self):
        servers = settings_get('servers', default=[])
        self.items = [key for key in servers.keys()]
        sublime.active_window().show_quick_panel([item.upper() for item in self.items],self.change)