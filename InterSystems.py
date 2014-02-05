#aponxi
import sys
import os
import subprocess
import sublime_plugin
import sublime

def default_instance_name_get():
    ccontrol = subprocess.Popen(['ccontrol', 'default'],stdout=subprocess.PIPE)
    stdout = ccontrol.communicate()[0]
    return stdout.decode('UTF-8').split('\n')[0]

def path_get():
    instanceName = default_instance_name_get()
    ccontrol = subprocess.Popen(['ccontrol', 'qlist'],stdout=subprocess.PIPE)
    stdout = ccontrol.communicate()[0]
    instanceStrings = stdout.decode('UTF-8').split('\n')
    for instanceString in instanceStrings:
        instanceArray = instanceString.split('^')
        if instanceName.upper() == instanceArray[0]:
            return instanceArray[1]
    raise

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
    print(args, stdin)
    pipeStdin = subprocess.PIPE if stdin else None
    communicateArgs = [bytes(stdin,"UTF-8")] if stdin else []
    cstud = subprocess.Popen([sys.executable, '{0}/cstud/cstud.py'.format(os.path.dirname(os.path.realpath(__file__)))] + list(args), stdout=subprocess.PIPE, stdin=pipeStdin)
    return cstud.communicate(*communicateArgs)[0].decode('UTF-8')

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
        self.items = call_cstud('list').split('\n')
        sublime.active_window().show_quick_panel(self.items,self.download)

class UploadClassOrRoutine(sublime_plugin.ApplicationCommand):
    def run(self):
        view = sublime.active_window().active_view()
        text = view.substr(sublime.Region(0, view.size()))
        call_cstud('upload', '-', stdin=text)