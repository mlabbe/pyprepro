#!/usr/bin/env python

import os
import re
import sys
import glob
import mimetypes
import subprocess

from os.path import join as path_join

MAGIC_STR = '-|- build-edge:'
COMMON_RESERVED_KEYS = ('build-edge', 'rule', 'in', 'set')
VAR_DELIMITER = '%'

build_preamble = """# generated by pyprepro.py, an experimental builder
"""

build_rules = {
    # note: this only generates one single output. grc's Writefile() breaks it.
    'grc': {
        'command': 'grc --preserve-preamble $in -o $out',
        'description': 'grain generating $out file from $in',

        'reserved': [],
    },
    'tpl': {
        'command': 'tpl --preserve-preamble --trusted $in $flags -o $out',
        'description': 'tpl $out',

        # the list of keys that are not passed on to ninja directly
        'reserved': [],
    },
}

build_filename = './build.ninja'


def fatal(msg):
    print("fatal: " + msg, file=sys.stderr)
    sys.exit(1)

def find_arg_0param(expected_arg):
    for arg in sys.argv:
        if arg == expected_arg:
            return True

    return False


def get_build_edge_preamble(path):
    try:
        with open(path, "rb") as f:
            try:
                head = f.read(512).decode('utf-8')
            except UnicodeDecodeError:
                # likely binary
                return None

            return head

    except PermissionError:
        # permission denied on likely non-text files is a non-issue
        mime_type, _ = mimetypes.guess_type(path)
        if mime_type == None:
            # unguessable, warn only
            print("pyprepro permission denied: unable to guess mime type for file '%s'" % path, file=sys.stderr)
            return None

        if mime_type.startswith("text/"):
            fatal("permission denied reading file '%s'" % path)

        # it's likely a binary, so just continue
        return None

def get_all_variables_from_preamble(preamble, path, root_dir):

    if 'set' not in preamble:
        return {}


    vars = {}
    # add in special var 'root'
    vars['root'] = root_dir

    # find all set lines, and create a dictionary of their key/values
    for set_line in preamble['set']:

        parts = set_line.split('=')
        if len(parts) != 2:
            fatal("pyprepro 'set' line failed to parse for file '%s'" % path)

        key = parts[0].strip()
        if key in vars:
            fatal("pyprepro 'set' line attempted to reassign already-set value '%s' for file '%s'" % \
                  (key, path))
        value = parts[1].strip()

        parsed_value = parse_dollarsign_vars(value, vars, path)

        vars[key] = parsed_value

    return vars

def parse_dollarsign_vars(s, vars, path):
    """
    Given a string like '%foo abc' search for vars['foo'] to expand it.
    """
    VAR_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    PATTERN = f'[^{re.escape(VAR_CHARS)}]'
    out = ''

    reading = False
    for i in range(0, len(s)):
        c = s[i]

        if c not in VAR_CHARS:
            reading = False

        if reading:
            continue

        if c == VAR_DELIMITER:
            reading = True
            scanned_var = re.split(PATTERN, s[i+1:])[0]
            if len(scanned_var) == 1:
                out += c
                reading = False
                continue

            if scanned_var not in vars:
                fatal("found var '%c%s' in '%s', but it not set before reference'" % \
                      (VAR_DELIMITER, scanned_var, path))
            else:
                out += vars[scanned_var]
        else:
            out += c

    return out


def get_in_files_from_preamble_in_line(in_lines, vars, out_dir, src_path):
    file_list = []

    # pretty hacky - assemble all in_lines into one long in_line value
    in_line = ""
    for line in in_lines:
        in_line += line + " "

    # now split it back into individual entries

    for entry in in_line.split():

        glob_path = parse_dollarsign_vars(entry, vars, src_path)

        globbed_paths = glob.glob(glob_path)
        if len(globbed_paths) == 0:
            fatal("glob_path resulted in no files: '%s' for path '%s'" % (glob_path, src_path))

        for path in glob.glob(glob_path):
            relative_path = resolve_relative_path(root_dir, path)
            file_list.append(relative_path)

        #file_list.extend(glob.glob(glob_path))

    return file_list

def args_for_in_files(in_files, prepend_str):
    files = []
    for file in in_files:
        files.append(prepend_str + file)

    return files


def resolve_relative_path(root_dir, relative):
    # root_dir is presumed to be absolute
    relative_abs = os.path.abspath(os.path.join(root_dir, relative))

    if os.path.commonpath([root_dir]) == os.path.commonpath([root_dir, relative_abs]):
        # relative_abs is under root_dir
        # return the part part of the path that is not common between the two
        #
        # eg:
        # root_dir = /home/foo
        # relative_abs = /home/foo/bar/baz.txt
        #
        # return bar/baz.txt
        return os.path.relpath(relative_abs, root_dir)
    else:
        return None

#
# generate ninja.build
#
root_dir = os.path.abspath(os.getcwd())
f = open(build_filename, "w")
print(build_preamble, file=f)
print(f"root={root_dir}\n", file=f)
for rule in build_rules:
    print("rule %s" % rule, file=f)
    for item, value in build_rules[rule].items():
        print("  %s = %s" % (item, value), file=f)
    print("\n", file=f)

print("# end rules", file=f)

#
# get scannable files
#
scannable_files = []
for root, dirs, files in os.walk("./"):
    if root.startswith('./.git'):
        continue
    for file in files:
        if file[0] != '.':
            scannable_files.append(path_join(root, file))

re_preamble_keyvalue= re.compile(r'-\|-\s(.+?):\s*(.+)')


#
# scan
#
error_count = 0
for path in scannable_files:
    out_dir = os.path.dirname(path)
    if path.startswith('./'):
        path = path[2:]

    head = get_build_edge_preamble(path)
    if head == None:
        continue

    # this file has a build edge preamble
    if MAGIC_STR in head:

        preamble = {}

        # hacky: will continue amalgamating -|- lines even after a space
        for line in head.split('\n'):
            match = re_preamble_keyvalue.search(line)
            if match:
                k = match.group(1).rstrip()
                v = match.group(2).rstrip()
                if k in preamble:
                    preamble[k].append(v)
                else:
                    preamble[k] = [v]
                #preamble[match.group(1).rstrip()] = match.group(2).rstrip()

        if 'build-edge' not in preamble or preamble['build-edge'][0] != 'ninja':
            print("unworkable build edge for '%s'. pyprepro only does 'ninja'" % path)
            if 'build-edge' in preamble:
                print("got: '%s'\n" % preamble['build-edge'])

            error_count += 1
            continue

        # set all variables from the 'set' key
        vars = get_all_variables_from_preamble(preamble, path, root_dir)

        # generate build edge for this file's preamble
        in_files = get_in_files_from_preamble_in_line(preamble['in'], vars, out_dir, path)
        if len(in_files) == 0:
            print("Warning: %s in line produced 0 files", path)

        print(f"\nbuild {path}: {preamble['rule'][0]} {' '.join(in_files)} | {build_filename}", file=f)

        # create ninja build variables out of any other build spec
        # lines not used above
        for var_line in sorted(preamble.keys()):
            # common reserved words
            if var_line in COMMON_RESERVED_KEYS: continue

            # build type reserved words
            reserved_words = build_rules[preamble['rule'][0]]['reserved']
            if var_line in reserved_words: continue

            # not a reserved word, pass it on as a ninja variable

            # if a line is specified more than once, aggregate it into one assignment with spaces
            print(f"  {var_line} = {' '.join(preamble[var_line])}", file=f)

f.close()

if error_count != 0:
    fatal("%d errors found. exiting without calling ninja" % error_count)


if not find_arg_0param('--skip-ninja'):
    verbose_arg = ''
    cmd = ['ninja']
    if find_arg_0param('-v'):
        cmd.append('-v')

    cp = subprocess.run(cmd)
    sys.exit(cp.returncode)
