#!/bin/bash

_cstud_complete()
{
    local cur=${COMP_WORDS[COMP_CWORD]}
    number=$(history | tail -n1 | cut -f3 -d' ')
    varName="cache$number"
    cached=${!varName}
    if [[ -z "$cached" ]]; then
        completions=$(cstud list)
        cached=$(compgen -W "$completions")
        export cache$number="$cached"
    fi
    COMPREPLY=( $(compgen -W "$cached" -- $cur) )
}

complete -o default -F _cstud_complete cstud