cdev
====

InterSystems Cache Development API

To install the server-side components, run this absurd thing:

    zn "%SYS"  s b=##class(SYS.Database).%OpenId($zu(12,"cachelib")),bk=b.ReadOnly,b.ReadOnly=0  d b.%Save()  s s="Github_CDEV",l="/brandonhorst/ldev/master/",jf="json/",jn="%CDEV.JSON.",f="base,boolean,list,null,number,object,stream",if="includes.inc",sf="server/",sn="%CDEV.Server"  d ##class(Security.SSLConfigs).Create(s)  s r=##class(%Net.HttpRequest).%New(),r.Server="raw.github.com",r.Https=1,r.SSLConfiguration=s  f i=1:1:$l(f,",") { s t=$p(f,",",i),tn=jn_$zcvt($e(t),"U")_$e(t,2,99)  d r.Get(l_jf_t_".cls")  s d=$replace(r.HttpResponse.Data.Read(),$c(10),$c(13,10))  d ##class(%Compiler.UDL.TextServices).SetTextFromString(,tn,d)  d $system.OBJ.Compile(tn,"c-d") }  d r.Get(l_jf_if)  s i=##class(%Routine).%New(jn_$zcvt($e(if),"U")_$e(if,2,*-3)_$zcvt($e(if,*-2,99),"U"))  d i.CopyFromAndSave(r.HttpResponse.Data)  d r.Get(l_sf_$zcvt(sn,"O","URL")_".cls")  s d=$replace(r.HttpResponse.Data.Read(),$c(10),$c(13,10))  d ##class(%Compiler.UDL.TextServices).SetTextFromString(,sn,d)  d $system.OBJ.Compile(sn,"c-d")  s b.ReadOnly=bk  d b.%Save()

Only runs on Cache 2014.1+, and only on Windows (as %Compiler.UDL.TextServices has not yet been ported).