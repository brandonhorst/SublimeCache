#aponxi
import sys
import os
import subprocess
import sublime_plugin
import sublime


def settings_get(name, default=None):
    # load up the plugin settings
    plugin_settings = sublime.load_settings('CoffeeScript.sublime-settings')
    # project plugin settings? sweet! no project plugin settings? ok, well promote plugin_settings up then
    if sublime.active_window() and sublime.active_window().active_view():
        project_settings = sublime.active_window().active_view().settings().get("CoffeeScript")
    else:
        project_settings = {}

    # what if this isn't a project?
    # the project_settings would return None (?)
    if project_settings is None:
        project_settings = {}

    setting = project_settings.get(name, plugin_settings.get(name, default))
    return setting



class DownloadClassOrRoutine(sublime_plugin.ApplicationCommand):

    def run(self):
        sublime.error_message("test")
