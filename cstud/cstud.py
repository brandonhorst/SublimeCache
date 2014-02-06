#!/usr/bin/env python3

import argparse
import math
import os
import os.path
import re
import string
import subprocess
import sys
import signal
import threading

signal.signal(signal.SIGPIPE,signal.SIG_DFL) 

class CstudException(Exception):
    def __init__(self,code,value):
        self.code = code
        self.value = value
    def __str__(self):
        return "cstud Error #{0}: {1}".format(self.code,self.value)

def info_(bindings_location=False, **kwargs):
    if bindings_location:
        details = InstanceDetails()
        print(details.latest_location)

class InstanceDetails:
    def __init__(self, instanceName=None, host=None, super_server_port=None, web_server_port=None):
        localInstances = self.getLocalInstances()

        if not instanceName and not host and not super_server_port and not web_server_port:
            instanceName = self.getDefaultCacheInstanceName()

        if instanceName:
            instance = self.getThisInstance(localInstances,instanceName)
            host = '127.0.0.1'
            super_server_port = instance['super_server_port']
            web_server_port = instance['web_server_port']

        self.latest_location = self.getLatestLocation(localInstances)
        self.host = host
        self.super_server_port = int(super_server_port)
        self.web_server_port = int(web_server_port)


    def getLocalInstances(self):
        try: 
            ccontrol = subprocess.Popen(['ccontrol', 'qlist'],stdout=subprocess.PIPE)
            stdout = ccontrol.communicate()[0]
            instanceStrings = stdout.decode('UTF-8').split('\n')

            localInstances = []
            for instanceString in instanceStrings:
                if instanceString:
                    instanceArray = instanceString.split('^')
                    trueInstanceArray = instanceArray[0:3] + instanceArray[5:7]
                    instance = dict(zip(['name','location','version','super_server_port','web_server_port'],trueInstanceArray))
                    localInstances += [instance]
            return localInstances
        except FileNotFoundError:
            raise CstudException(103,"ccontrol not on PATH")
        except:
            raise CstudException(201,"ccontrol qlist output not expected")


    def getThisInstance(self,localInstances,instanceName):
        for instance in localInstances:
            if instance['name'] == instanceName.upper():
                return instance
        else:
            raise CstudException(102,"Invalid Instance Name: {0}".format(instanceName.upper()))

    def getLatestLocation(self,localInstances):
        maxVersion = 0
        maxLocation = ""
        for instance in localInstances:
            versionInt = self.convertVersionToInteger(instance['version'])
            if versionInt > maxVersion:
                maxVersion = versionInt
                maxLocation = instance['location']
        return maxLocation

    def getDefaultCacheInstanceName(self):
        try:
            ccontrol = subprocess.Popen(['ccontrol','default'],stdout=subprocess.PIPE)
            stdout = ccontrol.communicate()[0]
            return stdout.decode('UTF-8').split('\n')[0]
        except FileNotFoundError:
            raise CstudException(103,"ccontrol not on PATH")

    def convertVersionToInteger(self,version):
        splitVersion = version.split('.')
        splitVersion += ['']*(5-len(splitVersion))
        paddedArray = [num.zfill(4) for num in splitVersion]
        return int(''.join(paddedArray))

class Credentials:
    def __init__(self, username, password, namespace):
        self.username = username
        self.password = password
        self.namespace = namespace

def getPythonBindings(latest_location,force):

    #Returns True if it was not already there, false if it was
    def addToEnvPath(env,location):
        changedIt = True
        if not os.environ.get(env):
            os.environ[env] = location
        elif not location in os.environ.get(env):
            os.environ[env] += ":"+location
        else:
            changedIt = False
        return changedIt

    binDirectory = os.path.join(latest_location,'bin')
    if sys.platform.startswith('linux'):
        libraryPath = 'LD_LIBRARY_PATH'
    elif sys.platform == 'darwin':
        libraryPath = 'DYLD_LIBRARY_PATH'
    else:
        sys.exit("Unsupported Platform")
    rerun = addToEnvPath(libraryPath,binDirectory) and addToEnvPath('PATH',binDirectory)
    if rerun:
        os.execve(os.path.realpath(__file__), sys.argv, os.environ)

    try:
        if force:
            raise ImportError
        import intersys.pythonbind3
    except ImportError:
        try:
            installerDirectory = os.path.join(latest_location, 'dev', 'python')
            installerPath = os.path.join(installerDirectory, 'setup3.py')
            installerProcess = subprocess.Popen([sys.executable, installerPath, 'install'], cwd=installerDirectory, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL)
            installerProcess.communicate(bytes(latest_location, 'UTF-8'))
            import intersys.pythonbind3
        except Exception as ex:
            raise CstudException(301, 'Error installing Python Bindings: {0}'.format(ex))

    return intersys.pythonbind3

class Cache:
    def __init__(self, bindings, credentials, instanceDetails,verbosity=0):
        self.pythonbind = bindings
        self.credentials = credentials
        self.instance = instanceDetails

        url = '%s[%i]:%s' % (self.instance.host, self.instance.super_server_port, self.credentials.namespace)
        conn = bindings.connection()
        try:
            conn.connect_now(url, self.credentials.username, self.credentials.password, None)
        except Exception as ex:
            raise CstudException(401, 'Unable to connect to Cache: {0}'.format(ex))

        self.database = bindings.database(conn)
        self.verbosity = verbosity

    def deleteRoutine(self,routineName):
        self.database.run_class_method('%Library.Routine',"Delete",[routineName])

    def deleteClass(self,className):
        flags = "d" if self.verbosity else "-d"
        self.database.run_class_method('%SYSTEM.OBJ', 'Delete', [className,flags])

    def routineExists(self,routineName):
        exists = self.database.run_class_method('%Library.Routine','Exists',[routineName])
        return exists

    def classExists(self,className):
        exists = self.database.run_class_method('%Dictionary.ClassDefinition', '%ExistsId', [className])
        return exists

    def classNameForText(self,text):
        match = re.search(r'^Class\s',text,re.MULTILINE)
        if match:
            classNameIndexBegin = match.end()
            classNameIndexEnd = text.find(' ', classNameIndexBegin)
            className = text[classNameIndexBegin:classNameIndexEnd]
            return className
        return None
            
    def uploadRoutine(self,text):
        match = re.search(r'^(#; )?(?P<routine_name>(\w|%|\.)+)',text,re.MULTILINE)
        routineName = match.group('routine_name')

        # if routineExists(database,routineName):
            # if verbose: print('Deleting %s' % routineName)
            # deleteRoutine(database,routineName)

        routine = self.database.run_class_method('%Library.Routine', '%New', [routineName])

        crlfText = text.replace('\n','\r\n')

        self.writeStream(routine,crlfText)

        if self.verbosity: print('Uploading %s' % routineName)
        flags = "ckd" if self.verbosity else "ck-d"
        routine.run_obj_method('Save',[])
        routine.run_obj_method('Compile',[flags])

    def uploadClass(self,text):
        stream = self.database.run_class_method('%Stream.GlobalCharacter', '%New', [])
        name = self.classNameForText(text)

        if self.classExists(name):
            self.deleteClass(name)

        crlfText = text.replace('\n','\r\n')

        self.writeStream(stream,crlfText)

        result = self.database.run_class_method('%Compiler.UDL.TextServices', 'SetTextFromStream',[None, name, stream])
        if self.verbosity: print('Uploading %s: %s' % (name, result))
        flags = "ckd" if self.verbosity else "ck-d"
        self.database.run_class_method('%SYSTEM.OBJ','Compile',[name,flags])

    def uploadOnce(self,text):
        name = self.classNameForText(text)
        if name:
            self.uploadClass(text)
        else:
            self.uploadRoutine(text)

    def upload_(self,files):
        for openFile in files:
            text = openFile.read()
            self.uploadOnce(text)

    def readStream(self,stream):
        total = ""
        while True:
            content = stream.run_obj_method('Read',[])
            if content:
                if type(content) != str:
                    content = content.decode('utf-8')
                lfcontent = content.replace('\r\n','\n')
                total = total + lfcontent
            else:
                break
        return total

    def writeStream(self,stream,data):
        for chunk in self.chunkString(data):
            stream.run_obj_method('Write',[chunk])

    def chunkString(self,string,chunkSize=32000):
        return [string[i:i+chunkSize] for i in range(0, len(string), chunkSize)]

    def downloadClass(self,className):
        stream = self.database.run_class_method('%Stream.GlobalCharacter', '%New', [])
        argList = [None,className,stream] #the last None is byref
        self.database.run_class_method('%Compiler.UDL.TextServices', 'GetTextAsStream', argList)
        outputStream = argList[2]
        return self.readStream(outputStream)

    def downloadRoutine(self,routineName):
        routine = self.database.run_class_method('%Library.Routine','%OpenId',[routineName])
        return self.readStream(routine)

    def downloadOnce(self,name):
        content = self.downloadClass(name)
        if not content:
            content = self.downloadRoutine(name)
        return content

    def download_(self,names):
        for name in names:
            print(self.downloadOnce(name))

    def executeCode(self,code):
        stream = self.database.run_class_method('%Stream.GlobalCharacter', '%New', [])
        className = "ISCZZZZZZZZZZZZZZCSTUD.cstud"
        methodName = "xecute"
        classCode = """Class {0} Extends %RegisteredObject {{
        ClassMethod {1}() {{
            {2}
        }}
        }}
        """.format(className,methodName,code).replace("\n","\r\n")

        if self.classExists(className):
            self.deleteClass(className)

        self.writeStream(stream,classCode)

        self.database.run_class_method('%Compiler.UDL.TextServices', 'SetTextFromStream',[None, className, stream])
        flags = "ckd" if self.verbosity else "ck-d"
        self.database.run_class_method('%SYSTEM.OBJ','Compile',[className,flags])
        self.database.run_class_method(className,methodName,[])
        print()

    def executeFile(self,theFile):
        self.executeCode(theFile.read())

    def execute_(self,inline,files,stdin):
        if inline:
            self.executeCode(inline)
        if stdin:
            inlineCode = sys.stdin.read().replace("\n","\r\n")
            self.executeCode(inlineCode)
        for f in files:
            print(self.executeFile(f))

    def editOnce(self,name):
        initialContent = self.downloadOnce(name)

        editor = subprocess.Popen([os.environ['EDITOR']], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

        finalContentTuple = editor.communicate(bytes(initialContent,'UTF-8'))
        finalContent = finalContentTuple[0].decode('UTF-8')

        self.uploadOnce(finalContent)

    def edit_(self,names):
        threads = [threading.Thread(target=self.editOnce, args=[name]) for name in names]
            
        [thread.start() for thread in threads]
        [thread.join() for thread in threads]

    ### accepts runQuery("SELECT * FROM SAMPLE.PERSON") or runQuery("%SYS.Namespace::List")
    def runQuery(self, sqlOrName):
        query = self.pythonbind.query(self.database)
        if '::' in sqlOrName:
            query.prepare_class(*sqlOrName.split('::'))
        else:
            query.prepare(sqlOrName)
        sql_code = query.execute()
        results = []
        while True:
            cols = query.fetch([None])
            if len(cols) == 0: break
            results.append(cols)
        return results

    def listClasses(self,system):
        sql = 'SELECT Name FROM %Dictionary.ClassDefinition'
        results = self.runQuery(sql)
        [print(col[0]) for col in results]

    def listRoutines(self,type,system):
        sql = "SELECT Name FROM %Library.Routine_RoutineList('*.{0},%*.{0}',1,0)".format(type)
        results = self.runQuery(sql)
        [print(col[0]) for col in results]

    def listNamespaces(self):
        sql = '%SYS.Namespace::List'
        results = self.runQuery(sql)
        [print(col[0]) for col in results]

    def list_(self,listFunction,types=None,system=False):
        if listFunction == 'classes':
            self.listClasses(system)
            
        elif listFunction == 'routines':
            if types == None:
                types = ['mac','int','inc','bas']
            for theType in types:
                self.listRoutines(theType,system)

        elif listFunction == 'namespaces':
            self.listNamespaces()

    def export_(self,names,output=None):
        namesWithCommas = ",".join(names)
        flags = 'd' if self.verbosity else '-d'
        args = [namesWithCommas, None, flags]
        self.database.run_class_method('%SYSTEM.OBJ', 'ExportToStream', args)
        resultStream = args[1]
        print(self.readStream(resultStream), file=output)

    def import_(self,files):
        for file_ in files:
            text = file_.read()
            stream = self.database.run_class_method('%Stream.GlobalCharacter','%New',[])
            self.writeStream(stream,text)
            flags = 'ckd' if self.verbosity else 'ck-d'
            self.database.run_class_method('%SYSTEM.OBJ', 'LoadStream', [stream, flags])

    def loadWSDLFromURL(self,url):
        reader = self.database.run_class_method('%SOAP.WSDL.Reader','%New',[])
        reader.run_obj_method('Process',[url])

    def loadWSDL_(self,urls):
        for url in urls:
            self.loadWSDLFromURL(url)


def __main():
    mainParser = argparse.ArgumentParser()

    mainParser.add_argument('-V', '--verbose', action='store_const', const=1, help='output details')
    mainParser.add_argument('-U', '--username', type=str, default='_SYSTEM')
    mainParser.add_argument('-P', '--password', type=str, default='SYS')
    mainParser.add_argument('-N', '--namespace', type=str, default='USER')
    specificationGroup = mainParser.add_mutually_exclusive_group()
    specificationGroup.add_argument('-I', '--instance', type=str, default=None)
    locationGroup = specificationGroup.add_argument_group('location')
    locationGroup.add_argument('-H', '--host', type=str)
    locationGroup.add_argument('-S', '--super-server-port', type=int)
    locationGroup.add_argument('-W', '--web-server-port', type=int)
    mainParser.add_argument('--force-install', action='store_true')

    subParsers = mainParser.add_subparsers(help='cstud commands',dest='function')

    uploadParser = subParsers.add_parser('upload', help='Upload and compile classes or routines')
    uploadParser.add_argument("files", metavar="F", type=argparse.FileType('r'), nargs="+", help="files to upload")

    downloadParser = subParsers.add_parser('download', help='Download classes or routines')
    downloadParser.add_argument("names", metavar="N", type=str, nargs="+", help="Classes or routines to download")

    importParser = subParsers.add_parser('import', help='Upload and compile classes or routines')
    importParser.add_argument("files", metavar="F", type=argparse.FileType('r'), nargs="+", help="Files to import")

    exportParser = subParsers.add_parser('export', help='Upload and compile classes or routines')
    exportParser.add_argument("-o", "--output", type=argparse.FileType('w'), help='File to output to. STDOUT if not specified.')
    exportParser.add_argument("names", metavar="N", type=str, nargs="+", help="Classes or routines to export")

    executeParser = subParsers.add_parser('execute', help='Execute arbitrary COS code')
    executeParser.add_argument('-i', '--inline', type=str, help='Take code from stdin')
    executeParser.add_argument('-', dest="stdin", action='store_true', help='Take code from stdin')
    executeParser.add_argument("files", metavar="F", type=str, nargs="*", help="Execute routine specified in a file")

    editParser = subParsers.add_parser('edit', help='Download classes')
    editParser.add_argument("names", metavar="N", type=str, nargs="+", help="Classes or routines to edit")

    listParser = subParsers.add_parser('list', help='list server details')
    listSubParsers = listParser.add_subparsers(help='list options',dest='listFunction')

    listClassesParser = listSubParsers.add_parser('classes', help='List all classes and routines in namespace')
    listClassesParser.add_argument('-s','--noSystem',action='store_false', help='hide system classes',dest="system")

    listClassesParser = listSubParsers.add_parser('routines', help='List all classes and routines in namespace')
    listClassesParser.add_argument('-t','--type',action='append',help='mac|int|obj|inc|bas',dest="types",choices=['obj','mac','int','inc','bas'])
    listClassesParser.add_argument('-s','--noSystem',action='store_false', help='hide system classes',dest="system")

    listNamespacesParser = listSubParsers.add_parser('namespaces', help='List all classes and routines in namespace')

    loadWSDLParser = subParsers.add_parser('loadWSDL', help='Load a WSDL from a URL or a file, and create classes')
    loadWSDLParser.add_argument('urls', nargs='+', type=str, help='specify a URL')

    infoParser = subParsers.add_parser('info', help='Get configuration information')
    infoParser.add_argument('-l','--bindings-location', action='store_true', help='Print location of latest Cache instance installed')


    results = mainParser.parse_args()
    kwargs = dict(results._get_kwargs())

    function = kwargs.pop('function')
    if function == 'info':
        info_(**kwargs)
    else:
        instance = InstanceDetails(kwargs.pop('instance'), kwargs.pop('host'), kwargs.pop('super_server_port'), kwargs.pop('web_server_port'))
        bindings = getPythonBindings(instance.latest_location,force=kwargs.pop('force_install'))
        credentials = Credentials(kwargs.pop('username'), kwargs.pop('password'), kwargs.pop('namespace'))
        cacheDatabase = Cache(bindings, credentials, instance, kwargs.pop('verbose'))
        if function:
            getattr(cacheDatabase,function + '_')(**kwargs)

if __name__ == "__main__":
    try:
        __main()
    except CstudException as ex:
        print(ex)