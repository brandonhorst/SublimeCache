Class %CDEV.Server Extends %CSP.REST
{
    XData UrlMap [ XMLNamespace = "http://www.intersystems.com/urlmap" ]
    {
        <Routes>
            <Route Url="/namespaces" Method="GET" Call="GetNamespaceList" />
            <Route Url="/namespaces/:namespace" Method="GET" Call="GetNamespace" />
            <Route Url="/namespaces/:namespace/files" Method="GET" Call="GetFileList" />
            <Route Url="/namespaces/:namespace/files" Method="PUT" Call="PutNewFile" />
            <Route Url="/namespaces/:namespace/files/:filename" Method="GET" Call="GetFile" />
            <Route Url="/namespaces/:namespace/files/:filename" Method="PUT" Call="PutFile" />
            <Route Url="/namespaces/:namespace/files/:filename" Method="POST" Call="FileAction" />
            <Route Url="/namespaces/:namespace/files/:filename/generated" Method="GET" Call="GetGenerated" />
        </Routes>
    } 

ClassMethod GetNamespaceList() As %Status
{
    s rs = ..DoSQL("%SYS.Namespace::List")
    s results = ##class(%ListOfDataTypes).%New()
    while rs.%Next() {
        s obj = ##class(%ZEN.proxyObject).%New()
        s obj.name = rs.%GetData(1)
        s obj.id = ..CreatePath("namespaces", $zcvt(obj.name,"L"))
        s obj.files = obj.id _ "/files"
        d results.Insert(obj)
    }

    d ..SendJSON(results)
    q $$$OK
}

ClassMethod GetFileList(namespace As %String) As %Status
{
    n $namespace
    s $namespace = namespace

    s sql = "SELECT Name||'.CLS' FROM %Dictionary.ClassDefinition"
    s results = ##class(%ListOfDataTypes).%New()
    s rs = ..DoSQL(sql)
    while rs.%Next() {
        s obj = ##class(%ZEN.proxyObject).%New()
        s obj.name = rs.%GetData(1)
        s obj.id = ..CreatePath("namespaces", namespace, "files", obj.name)
        d results.Insert(obj)
    }

    d ..SendJSON(results)
    q $$$OK
}

ClassMethod GetNamespace(namespace As %String) As %Status
{
    s obj = ##class(%ZEN.proxyObject).%New()
    s obj.id = ..CreatePath("namespaces", namespace)
    s obj.files = ..CreatePath("namespaces", namespace, "files")
    d ..SendJSON(obj)
    q $$$OK
}

ClassMethod GetFile(namespace As %String, filename As %String)
{
    n $namespace
    s $namespace = namespace

    s classname = $e(filename,1,*-4)

    if ##class(%Dictionary.ClassDefinition).%ExistsId(classname)
    {
        d ##class(%Compiler.UDL.TextServices).GetTextAsStream(,classname,.classStream) 
        s result = ##class(%ZEN.proxyObject).%New()
        s result.id = ..CreatePath("namespaces", namespace, "files", filename)
        s result.generated = result.id _ "/generated"
        s result.name = classname
        s result.content = classStream
        d ..SendJSON(result)
    } else {
        s %response.Status = "440 File Not Found"
    }
    q $$$OK
}

ClassMethod PutFile(namespace As %String, filename As %String)
{
    n $namespace
    s $namespace = namespace

    s classname = ..FileName(filename)

    s requestObject = ..GetRequest()
    i $isobject(requestObject.content) {
        s sc = ##class(%Compiler.UDL.TextServices).SetTextFromStream(,classname,requestObject.content) 
    } else {
        s sc = ##class(%Compiler.UDL.TextServices).SetTextFromString(,classname,requestObject.content) 
    }

    i $$$ISERR(sc) {
        s %response.Status = "441 Invalid File"
    } else {
        d ..GetFile(namespace, filename)
    }
    q sc
}

ClassMethod PutNewFile(namespace As %String)
{
    s requestObject = ..GetRequest()
    d ..PutFile(namespace, requestObject.name)
}

ClassMethod FileAction(namespace As %String, filename As %String)
{
    n $namespace
    s $namespace = namespace

    s classname = ..FileName(filename)
    s requestObject = ..GetRequest()
    s result = ##class(%ZEN.proxyObject).%New()
    if request.action = "compile"
    {
        d $system.OBJ.Compile(classname, request.spec_"-d", .errorlog)
        i errorlog {
            s result.success = 0
            s result.errors = ##class(%ListOfDataTypes).%New()
            f i=1:1:errorlog
            {
                d result.errors.Insert(errorlog(i))
            }
        } else {
            s result.success = 1
        }
    }
    d ..SendJSON(result)
    q $$$OK
}

ClassMethod GetGenerated(namespace As %String, filename As %String)
{
    s rs = ..DoSQL("")
    s type = ..FileExtension(filename)
    s file = ..FileName(filename)
    s results = ##class(%ListOfDataTypes).%New()
    s genFileList = ##class(%RoutineMgr).GetOther(file,type)
    i $l(genFileList)
    {
        f i=1:1:$l(genFileList, ",")
        {
            s obj = ##class(%ZEN.proxyObject).%New()
            s obj.name = $p(genFileList, ",", i)
            s obj.id = ..CreatePath("namespaces",namespace,"files",obj.name)
            d results.Insert(obj)
        }
    }
    d ..SendJSON(results)
    q $$$OK
}

ClassMethod FileExtension(filename As %String)
{
    q $p(filename, ".", *)
}
ClassMethod FileName(filename As %String)
{
    q $p(filename, ".", 1, *-1) 
}

ClassMethod CreatePath(components...) As %String
{
    s path = $e(%request.Application, 1, *-1)
    s i = ""
    f
    {
        s i = $o(components(i), 1, component)
        q:i=""
        s path = path _ "/" _ $zcvt(component,"O","URL")
    }
    q path
}

ClassMethod GetClassName(class)
{
    if $isobject(class)
    {
        //This banks on there not being 32k documentation, which is probably safe
        s firstPart = class.Read()
    } else {
        s firstPart = class
    }
    s regexString = "\nClass\s((\w|\.)+)\s" 
    s regex = ##class(%Regex.Matcher).%New(regexString,firstPart)
    d regex.Locate()
    q regex.Group(1)_".CLS"
}

ClassMethod SendJSON(object as %RegisteredObject) As %Status
{
    s %response.ContentType="application/json"
    d ##class(%ZEN.Auxiliary.jsonProvider).%WriteJSONFromObject(,object)
}

ClassMethod GetRequest() As %ZEN.proxyObject
{
    d ##class(%ZEN.Auxiliary.jsonProvider).%ConvertJSONToObject(%request.Content,,.request)
    q request
}

ClassMethod GetListFromSQL(sql as %String) As %ListOfDataTypes
{
    set result = ##class(%ListOfDataTypes).%New()
    s st = ##class(%SQL.Statement).%New()
    if $find(sql,"::") {
        d st.%PrepareClassQuery($p(sql,"::",1), $p(sql,"::",2))
    } else {
        d st.%Prepare(sql)
    }
    s rs = st.%Execute()
    while rs.%Next() {
        d result.Insert(rs.%GetData(1))
    }
    q result
}

ClassMethod DoSQL(sql as %String) As %SQL.StatementResult
{
    s st = ##class(%SQL.Statement).%New()
    if $find(sql,"::") {
        d st.%PrepareClassQuery($p(sql,"::",1), $p(sql,"::",2))
    } else {
        d st.%Prepare(sql)
    }
    s x = st.%Execute()
    q x
}

}