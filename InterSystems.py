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


def download_file(file_stub):
    file = current_instance().get_file(file_stub)
    syntax_name = 'UDL' if file.name.endswith('.cls') else 'COS'
    sublime.run_command('open_cache_code',
        {
            'text':file.content,
            'syntax_name': syntax_name,
            'name': file.name,
            'file': vars(file)
        })


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
            sublime.run_command('show_cache_errors', { 'errors': result.errors })
            return False

    def update(self,result):
        if result.success:
            success = self.compile(result.file)
            if success:
                syntax_name = 'UDL' if result.file.name.endswith('.cls') else 'COS'
                self.view.run_command('write_cache_code',
                    {
                        'text': result.file.content,
                        'syntax_name': syntax_name,
                        'name': result.file.name
                    })

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
            else:
                sublime.run_command('show_cache_errors', { 'errors': compile_result.errors })

    def download(self,index):
        if index >= 0:
            file_stub = self.files[index]
            download_file(file_stub)

    def run(self, edit):
        threading.Thread(target=self.go).start()

class RunSqlQuery(sublime_plugin.TextCommand):
    def resultSetToString(self, content):
        lines = ['|', '']
        for (header, column) in content.items():
            lines[0] += header

            i = 2
            for field in column:
                if len(lines) <= i:
                    lines.append('|')
                lines[i] += field
                i += 1
            max_len = max([len(line) for line in lines])
            lines = [line.ljust(max_len, ' ') + '|' for line in lines]
            lines[1] = '=' * (max_len + 1)

        lines.append('-' * len(lines[1]))
        output = '\n'.join(lines)
        return output

    def go(self, text):
        addresult = current_instance().add_query(current_namespace(), text)
        if addresult.success:
            executeresult = current_instance().execute_query(addresult.query)
            if executeresult.success:
                output = self.resultSetToString(executeresult.resultset)
                sublime.run_command('open_cache_output', {
                        'text': output,
                        'name': text
                    })
            else:
                sublime.run_command('show_cache_errors', { 'errors': executeresult.errors })
        else:
            sublime.run_command('show_cache_errors', { 'errors': addresult.errors })

    def run_query(self, text):
        threading.Thread(target=self.go, args=[text]).start()

    def run(self, edit):
        selection = self.view.sel()
        for region in selection:
            if region.empty():
                region = sublime.Region(0, self.view.size())
            text = self.view.substr(region)
            self.run_query(text)

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

            sublime.run_command('open_cache_code', {
                    'text': xml.content,
                    'syntax_name': "Export",
                    'name': "{0} Export".format(file.name)
                })

    def run(self, edit):
        threading.Thread(target=self.go).start()


class ShowCacheErrors(sublime_plugin.ApplicationCommand):
    def run(self, errors):
        window = sublime.active_window()
        panel = window.create_output_panel('InterSystems')
        window.run_command('show_panel', { 'panel': 'output.InterSystems' })
        panel.run_command('write_cache_error', { 'errortext': '\n'.join(errors) })

class WriteCacheError(sublime_plugin.TextCommand):
    def run(self, edit, errortext):
        self.view.insert(edit, 0, errortext)

class OpenCacheCode(sublime_plugin.ApplicationCommand):
    def run(self, text, syntax_name, name, file = None):
        window = sublime.active_window()
        view = window.new_file()
        view.run_command('write_cache_output',
            {
                'text': text,
                'syntax_file': 'Packages/InterSystems Cache/CacheColors/{0}.tmLanguage'.format(syntax_name),
                'name': name,
                'file': file
            })

class OpenCacheOutput(sublime_plugin.ApplicationCommand):
    def run(self, text, name):
        window = sublime.active_window()
        view = window.new_file()
        view.run_command('write_cache_output', {
                'text': text,
                'name': name
            })

class WriteCacheOutput(sublime_plugin.TextCommand):
    def run(self, edit, text, name, file = None, syntax_file = None):
        self.view.erase(edit, sublime.Region(0, self.view.size()))
        unix_text = text.replace('\r\n','\n')
        self.view.insert(edit, 0, unix_text)
        self.view.set_name(name)
        self.view.set_scratch(True)
        if syntax_file: self.view.set_syntax_file(syntax_file)
        if file: self.view.settings().set('file', file)
