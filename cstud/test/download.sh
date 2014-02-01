#!/bin/bash

../cstud.py -NSAMPLES -D/intersystems/latest download Sample.Person > download/Sample.Person.cls
../cstud.py -NSAMPLES -D/intersystems/latest download Sample.Employee > download/Sample.Employee.cls
../cstud.py -NSAMPLES -D/intersystems/latest download ZENTest.MVCFormTest > download/ZENTest.MVCFormTest.cls
../cstud.py -NSAMPLES -D/intersystems/latest download Cinema.Film > download/Cinema.Film.cls