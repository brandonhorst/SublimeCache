Class %CDEV.Server Extends %CSP.REST
{
    XData UrlMap [ XMLNamespace = "http://www.intersystems.com/urlmap" ]
    {
        <Routes>
            <Route Url="/namespaces" Method="GET" Call="GetNamespaces" />
            <Route Url="/files/:namespace" Method="GET" Call="GetFiles" />
            <Route Url="/files/:namespace/:filename" Method="GET" Call="GetFile" />
            <Route Url="/files/:namespace/:filename" Method="PUT" Call="PutFile" />
        </Routes>
    } 

ClassMethod GetNamespaces() As %Status
{
    s result = ..GetListFromSQL("%SYS.Namespace::List")

    d ..SendJSON(result)
    q $$$OK
}

ClassMethod GetFiles(namespace As %String) As %Status
{
    n $namespace
    s $namespace = namespace

    s sql = "SELECT Name FROM %Dictionary.ClassDefinition"
    s result = ..GetListFromSQL(sql)

    d ..SendJSON(result)
    q $$$OK
}

ClassMethod GetFile(namespace As %String, filename As %String)
{
    n $namespace
    s $namespace = namespace

    s className = filename
    if $zcvt($e(filename,*-3,*),"U") = ".CLS" {
        s className = $e(filename,1,*-4)
    }
    if ##class(%Dictionary.ClassDefinition).%ExistsId(className)
    {
        d ##class(%Compiler.UDL.TextServices).GetTextAsStream(,className,.classStream) 
        s result = ##class(%ZEN.proxyObject).%New()
        s result.content = classStream
        d ..SendJSON(result)
    } else {
        s %response.Status = "440 File Not Found"
    }
    q $$$OK
}

ClassMethod PutFile(namespace,filename)
{
    n $namespace
    s $namespace = namespace

    s className = filename
    if $zcvt($e(filename,*-3,*),"U") = ".CLS" {
        s className = $e(filename,1,*-4)
    }

    d ##class(%ZEN.Auxiliary.jsonProvider).%ConvertJSONToObject(%request.Content,,.requestObject)
    s className = ..GetClassName(requestObject.content)
    if $isobject(requestObject.content) {
        s sc = ##class(%Compiler.UDL.TextServices).SetTextFromStream(,className,requestObject.content) 
    } else {
        s sc = ##class(%Compiler.UDL.TextServices).SetTextFromString(,className,requestObject.content) 
    }

    if $$$ISERR(sc) {
        s %response.Status = "441 Invalid File"
    }
    q sc

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
    q regex.Group(1)
}

ClassMethod SendJSON(object as %RegisteredObject) As %Status
{
    s %response.ContentType="application/json"
    d ##class(%ZEN.Auxiliary.jsonProvider).%WriteJSONFromObject(,object)
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

}