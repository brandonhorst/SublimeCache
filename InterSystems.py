import sys
import os
import subprocess
import sublime_plugin
import sublime

def settings_get(name, default=None):
    plugin_settings = sublime.load_settings('InterSystems.sublime-settings')

    return plugin_settings.get(name,default)

def settings_set(name, value):
    plugin_settings = sublime.load_settings('InterSystems.sublime-settings')
    plugin_settings.set(name, value)
    sublime.save_settings('InterSystemsCache.sublime-settings')

def update_current_instance():
    global current_instance

    instance_name = settings_get('current-server')
    servers = settings_get('servers',{})
    server = servers.get(instance_name)

    current_instance = CacheInstance(**server)

cdevPath = '/Users/brandonhorst/Dropbox/Programming/cdev/client'
if cdevPath not in sys.path:
    sys.path += [cdevPath]
from cdev import CacheInstance
update_current_instance()

class InsertText(sublime_plugin.TextCommand):
    def run(self,edit,text,isClass,name):
        self.view.insert(edit,0,text)
        self.view.set_name(name)
        syntaxFile = "UDL" if isClass else "COS"
        self.view.set_syntax_file('Packages/CacheColors/{0}.tmLanguage'.format(syntaxFile))

class DownloadClassOrRoutine(sublime_plugin.ApplicationCommand):
    def download(self,index):
        if index >= 0:
            name = self.items[index]
            content = current_instance.get_file(name)['content'].replace("\r\n","\n")
            view = sublime.active_window().new_file()
            # isClass = index < self.classCount
            view.run_command('insert_text',{'text':content,'isClass':True,'name':name})
    def run(self):
        self.items = current_instance.get_files()
        # self.classCount = len(classes)
        # self.items = classes + routines
        sublime.active_window().show_quick_panel(self.items,self.download)

class UploadClassOrRoutine(sublime_plugin.ApplicationCommand):
    def run(self):
        view = sublime.active_window().active_view()
        text = view.substr(sublime.Region(0, view.size()))
        # call_cstud('upload', '-', stdin=text)

class ChangeCacheNamespace(sublime_plugin.ApplicationCommand):
    def change(self, index):
        if index >= 0:
            servers = settings_get('servers',{})
            serverName = settings_get('current-server')
            servers[serverName]['namespace'] = self.items[index]
            settings_set('servers',servers)
            update_current_instance()

    def run(self):
        self.items = current_instance.get_namespaces()
        sublime.active_window().show_quick_panel(self.items,self.change)

class ChangeCacheInstance(sublime_plugin.ApplicationCommand):
    def change(self,index):
        if index >= 0:
            settings_set('current-server',self.items[index])
            update_current_instance()
            
    def run(self):
        servers = settings_get('servers', default=[])
        self.items = [key for key in servers.keys()]
        sublime.active_window().show_quick_panel([item.upper() for item in self.items],self.change)