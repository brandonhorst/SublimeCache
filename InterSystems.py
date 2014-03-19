from .cdev import cdev

import json
import os
import re
import sys
import subprocess
import sublime_plugin
import sublime
import threading
import webbrowser

def settings_get(name, default=None, file='InterSystems.sublime-settings'):
    plugin_settings = sublime.load_settings(file)
    return plugin_settings.get(name, default)

def settings_set(name, value, file='InterSystems.sublime-settings'):
    plugin_settings = sublime.load_settings(file)
    plugin_settings.set(name, value )
    sublime.save_settings(file)

def cache_name(name, namespace_specific = False):
    if namespace_specific:
        return "{0}{1}{2}{3}".format(name, current_instance().host, current_instance().port, current_namespace().name)
    else:
        return "{0}{1}{2}".format(name, current_instance().host, current_instance().port)

def cache_get(name, default=None, namespace_specific = False):
    cacheName = cache_name(name, namespace_specific)

    return settings_get(cacheName, default, 'InterSystemsCache.sublime-settings')

def cache_set(name, value, namespace_specific = False):
    cacheName = cache_name(name, namespace_specific)

    settings_set(cacheName, value, 'InterSystemsCache.sublime-settings')

def current_namespace():
    namespace = cache_get("Namespace",{})
    if len(namespace):
        return cdev.Namespace(namespace)
    else:
        sublime.active_window().run_command('change_cache_namespace', current_namespace)

def current_instance():
    instance_name = settings_get('current-server')
    servers = settings_get('servers',{})
    server = servers.get(instance_name)

    return cdev.CacheInstance(**server)

class InsertText(sublime_plugin.TextCommand):
    def run(self, edit, text, isClass = False, name = None):
        self.view.erase(edit, sublime.Region(0, self.view.size()))
        self.view.insert(edit,0,text.replace("\r\n","\n"))
        self.view.set_name(name)
        self.view.set_syntax_file('Packages/InterSystems Cache/CacheColors/{0}.tmLanguage'.format("UDL" if isClass else "COS"))
        self.view.set_scratch(True)

def download_file(file_stub):
    file = current_instance().get_file(file_stub)
    view = sublime.active_window().new_file()
    isClass = file.name.endswith('.cls')
    view.run_command('insert_text',{'text':file.content,'isClass': isClass, 'name': file.name})
    view.settings().set('file',vars(file))


class DownloadClassOrRoutine(sublime_plugin.ApplicationCommand):
    def run(self):
        threading.Thread(target=self.go).start()

    def go(self):
        self.cached_files = [cdev.File(file) for file in cache_get('Files', [], True)]
        if len(self.cached_files):
            sublime.active_window().show_quick_panel([file.name for file in self.cached_files], self.download)
        #Update the Cache
        files = current_instance().get_files(current_namespace())
        if not len(self.cached_files):
            self.cached_files = files
            sublime.active_window().show_quick_panel([file.name for file in self.cached_files], self.download)
        cache_set('Files', [vars(file) for file in files], True)

    def download(self,index):
        if index >= 0:
            file_stub = self.cached_files[index]
            download_file(file_stub)


class UploadClassOrRoutine(sublime_plugin.ApplicationCommand):
    def get_class_name(self):
        match = re.search(r"^Class\s((\%|[a-zA-Z])(\w|\.)+)\s", self.text, re.MULTILINE)
        if match:
            return match.group(1) + ".cls"
        else:
            match = re.search(r"^;((\%|[a-zA-Z])(\w|\.)+)\s", self.text, re.MULTILINE)
            return None

    def compile(self, new_file):
        result = current_instance().compile_file(new_file,"ck")
        if result.success:
            sublime.status_message("Compiled {0}".format(result.file.name))
            return True
        else:
            panel = view.window().show_panel("output")
            panel.run_command('insert_text', {'text': result.errors, 'isClass': False, 'name': 'Compilation Results'})
            return False

    def update(self,result):
        if result.success:
            success = self.compile(result.file)
            if success:
                self.view.settings().set('file',vars(result.file))
                isClass = result.file.name.endswith('.cls')
                self.view.run_command('insert_text', {'text': result.file.content, 'isClass': isClass, 'name': result.file.name} )

    def take_name(self, name):
        if not x[-4] == '.':
            name += ".mac"
        result = current_instance().add_file(current_namespace(), name, self.text)
        self.update(result)

    def run(self):
        threading.Thread(target=self.go).start()

    def go(self):
        self.view = sublime.active_window().active_view()
        self.text = self.view.substr(sublime.Region(0, self.view.size())).replace('\n','\r\n')
        
        file_dict = self.view.settings().get('file', None)
        if file_dict:
            file = cdev.File(file_dict)
            file.content = self.text
            result = current_instance().put_file(file)
            self.update(result)
        else:
            class_name = self.get_class_name()
            if class_name:
                result = current_instance().add_file(current_namespace(), class_name, self.text)
                self.update(result)
            else:
                self.view.window().show_input_panel("Enter a name for this routine", "", self.take_name)

class OpenInBrowser(sublime_plugin.TextCommand):
    def run(self, edit):
        file = self.view.settings_get('file')
        if file and 'url' in file:
            webbrowser.open("http://{0}:{1}}{2}".format(current_instance().host, current_instance().port, file['url']))

class ChangeCacheNamespace(sublime_plugin.ApplicationCommand):
    def change(self, index):
        if index >= 0:
            cache_set('Namespace', vars(self.namespaces[index]))
            if self.callback:
                self.callback()


    def run(self, callback = None):
        self.callback = callback
        threading.Thread(target=self.go).start()

    def go(self):
        self.namespaces = current_instance().get_namespaces()
        sublime.active_window().show_quick_panel([namespace.name for namespace in self.namespaces], self.change)

class ChangeCacheInstance(sublime_plugin.ApplicationCommand):
    def change(self,index):
        if index >= 0:
            settings_set('current-server',self.items[index])
            
    def run(self):
        servers = settings_get('servers', default=[])
        self.items = [key for key in servers.keys()]
        sublime.active_window().show_quick_panel([item.upper() for item in self.items],self.change)

def get_file(view):
    view_file = view.settings().get('file', None)
    return cdev.File(view_file) if view_file else None

class OpenGeneratedFiles(sublime_plugin.TextCommand):
    def go(self):
        file = get_file(self.view)
        if file:
            compile_result = current_instance().compile_file(file, 'ck-u')
            if compile_result.success:
                self.files = current_instance().get_generated_files(compile_result.file)
                if len(self.files):
                    sublime.active_window().show_quick_panel([file.name for file in self.files], self.download)

    def download(self,index):
        if index >= 0:
            file_stub = self.files[index]
            download_file(file_stub)


    def run(self, edit):
        threading.Thread(target=self.go).start()

class LoadXml(sublime_plugin.TextCommand):
    def go(self):
        self.text = self.view.substr(sublime.Region(0, self.view.size()))
        operation = current_instance().add_xml(current_namespace(), self.text)
        download_file(operation.file)

    def run(self, edit):
        threading.Thread(target=self.go).start()

class ExportXml(sublime_plugin.TextCommand):
    def go(self):
        file = get_file(self.view)
        if file:
            xml = current_instance().get_xml(file)
            self.view.run_command('insert_text', { 'text':xml.content })

    def run(self, edit):
        threading.Thread(target=self.go).start()
