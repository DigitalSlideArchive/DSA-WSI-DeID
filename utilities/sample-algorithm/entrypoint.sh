#!/usr/bin/env bash

if [[ "$1" == "--list_cli" ]]; then
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    echo "{"
    first=1
    for xml_file in "$script_dir"/*.xml; do
        [ -e "$xml_file" ] || continue  # skip if no .xml files
        base="${xml_file##*/}"          # filename only
        base="${base%.xml}"             # remove .xml extension
        for ext in "" ".py" ".sh"; do
            candidate="$script_dir/$base$ext"
            if [ -x "$candidate" ]; then
                if [ $first -eq 0 ]; then
                    echo ","
                fi
                first=0
                printf '  "%s": {}' "$base"
                break
            fi
        done
    done
    echo
    echo "}"
elif [[ "$2" == "--xml" && -f "$1.xml" ]]; then
    cat "$1.xml"
elif [[ -x "$1" ]]; then
    exec "./$1" "${@:2}"
elif [[ -x "$1.py" ]]; then
    exec "./$1.py" "${@:2}"
elif [[ -x "$1.sh" ]]; then
    exec "./$1.sh" "${@:2}"
else
    echo "usage: entry_point.sh [-h] [--list_cli] <cli>"
    echo
    echo "positional arguments:"
    echo "  <cli>       CLI to run"
    echo
    echo "options:"
    echo "  -h, --help  show this help message and exit"
    echo "  --list_cli  Prints the json file containing the list of CLIs present"
fi
