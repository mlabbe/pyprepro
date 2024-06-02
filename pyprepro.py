#!/usr/bin/env python

import os
import re
import sys
import glob

from os.path import join as path_join

MAGIC_STR = '-|- build-edge:'

build_preamble = """# generated by pyprepro.py, an experimental builder
"""

build_rules = {
    # note: this only generates one single output. Writefile() breaks it.
    'grc': {
        'command': 'grc --preserve-preamble $in -o $out',
        'description': 'grain generating $out file from $in',
    },
    'tpl': {
        # todo: support empty vars and --name
        'command': 'tpl --preserve-preamble --name main.go.tmpl $in -o $out $vars_args',
        'description': 'tpl generating $out',
    },
}

build_filename = './build.ninja'


def fatal(msg):
    print("fatal: " + msg, file=sys.stderr)
    sys.exit(1)

def get_build_edge_preamble(path):
    with open(path, "rb") as f:
        try:
            head = f.read(512).decode('utf-8')
        except UnicodeDecodeError:
            return None
        return head

def get_in_files_from_preamble_in_line(in_line, root_dir, out_dir):
    file_list = []
    for entry in in_line.split():
        # entries can be relative to the ninja root, or relative to the out file
        if entry.startswith('$root'):
            glob_path = root_dir + entry[5:]
        else:
            glob_path = path_join(out_dir, entry)

        globbed_paths = glob.glob(glob_path)
        if len(globbed_paths) == 0:
            fatal("glob_path resulted in no files: %s" % glob_path)

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

print("# end rules\n", file=f)

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
                preamble[match.group(1)] = match.group(2)

        if 'build-edge' not in preamble or preamble['build-edge'] != 'ninja-rule':
            print("unworkable build edge. pyprepro only does ninja-rule")
            continue

        # generate build edge for this file's preamble
        in_files = get_in_files_from_preamble_in_line(preamble['in'], root_dir, out_dir)
        if len(in_files) == 0:
            print("Warning: %s in line produced 0 files", path)

        print(f"build {path}: {preamble['rule']} {' '.join(in_files)} | {build_filename}", file=f)

        # create ninja build variables out of any other build spec
        # lines not used above
        for var_line in sorted(preamble.keys()):
            if var_line in ('build-edge', 'rule', 'in'): continue

            if preamble['rule'] == 'tpl' and var_line == 'vars': continue

            
            print(f"  {var_line} = {preamble[var_line]}", file=f)

        # hack: handle tpl edge case, where vars is a list of paths relative to $out
        # but need to be '-i <path>', where path is relative to root
        if preamble['rule'] == 'tpl' and var_line in preamble['vars']:

            out_dir = os.path.dirname(path)
            var_line = ''
            for vars_file in preamble['vars'].split(' '):

                # vars can be relative to the ninja root, or relative to the out file
                if vars_file.startswith('$root'):
                    vars_path = root_dir + vars_file[5:]
                else:
                    vars_path = path_join(out_dir, vars_file)

                relative_var_file = resolve_relative_path(root_dir, vars_path)
                if relative_var_file == None:
                    # possibly we want files not under build root in the future? seems
                    # janky.
                    fatal("%s tpl has a var not under build root: %s" % (path, vars_file))

                if not os.path.isfile(relative_var_file):
                    fatal("%s tpl var file not found: %s" % (path, vars_file))


                # vars files needs --vars for each one
                var_line += ' --input-vars ' + relative_var_file
            print(f"  vars_args = {var_line} ", file=f)

f.close()
