#aponxi
import sys
import os
import subprocess
import sublime_plugin
import sublime

def settings_get(name, default=None):
    # load up the plugin settings
    plugin_settings = sublime.load_settings('InterSystemsCache.sublime-settings')
    # project plugin settings? sweet! no project plugin settings? ok, well promote plugin_settings up then
    if sublime.active_window() and sublime.active_window().active_view():
        project_settings = sublime.active_window().active_view().settings().get("InterSystemsCache")
    else:
        project_settings = {}

    # what if this isn't a project?
    # the project_settings would return None (?)
    if project_settings is None:
        project_settings = {}

    setting = project_settings.get(name, plugin_settings.get(name, default))
    return setting

def call_cstud(*args,stdin=None):
    instanceName = settings_get('current-server')
    servers = settings_get('servers',{})
    server = servers.get(instanceName)
    if not server:
        sublime.error_message("Cache Servers configured improperly")
        return None
    defaultArgs = [sys.executable, '{0}/cstud/cstud.py'.format(os.path.dirname(os.path.realpath(__file__))), '-V',
                   '-U', server['username'],
                   '-P', server['password'],
                   '-H', server['host'],
                   '-S', server['super-server-port'],
                   '-N', server['namespace'],
                   '-W', server['web-server-port']]

    pipeStdin = subprocess.PIPE if stdin else None
    communicateArgs = [bytes(stdin,"UTF-8")] if stdin else []
    cstud = subprocess.Popen(defaultArgs + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=pipeStdin)
    stdout,stderr = cstud.communicate(*communicateArgs)
    print(stdout, stderr)
    return stdout.decode('UTF-8')

def path_get():
    return call_cstud("info","-l")

bindingsPath = path_get()
os.environ['PATH'] = "{0}:{1}/bin".format(os.environ['PATH'],bindingsPath)
os.environ['DYLD_LIBRARY_PATH'] = "{0}:{1}/bin".format(os.environ['PATH'],bindingsPath)

class InsertText(sublime_plugin.TextCommand):
    def run(self,edit,text):
        self.view.insert(edit,0,text)

class DownloadClassOrRoutine(sublime_plugin.ApplicationCommand):
    def download(self,index):
        if index >= 0:
            name = self.items[index]
            results = call_cstud('download',name)
            view = sublime.active_window().new_file()
            view.run_command('insert_text',{'text':results})
    def run(self):
        self.items = call_cstud('list', 'classes').split('\n')
        self.items += call_cstud('list', 'routines').split('\n')
        sublime.active_window().show_quick_panel(self.items,self.download)

class UploadClassOrRoutine(sublime_plugin.ApplicationCommand):
    def run(self):
        view = sublime.active_window().active_view()
        text = view.substr(sublime.Region(0, view.size()))
        call_cstud('upload', '-', stdin=text)