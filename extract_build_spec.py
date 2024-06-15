#!/usr/bin/env python

# extract or detect build edge spec
# can be used with stdin, a file, or as an imported Python library

import os
import re
import sys
import argparse

from os.path import join as path_join

HEADER_CHUNK_BYTES = 512

re_preamble_keyvalue = re.compile(r'\|\|\s(.+?):\s*(.+)')

def detect_build_spec(input_data):
    try:
        chunk = input_data.read(HEADER_CHUNK_BYTES)
    except UnicodeDecodeError:
        # if it's not decodable it's not a build spec file
        return False

    match = re_preamble_keyvalue.search(chunk)
    return match != None

def extract_build_spec(input_data):
    found_build_edge_line = False
    started_match = False


    buf = ''

    for line in input_data:
        match = re_preamble_keyvalue.search(line)
        if match != None:
            found_build_edge_line = True

        if '||' in line and found_build_edge_line:
            started_match = True
        elif started_match == True:
            break

        buf += line

    if not found_build_edge_line:
        return ''
    else:
        return buf

def _get_stream(args):
    if args.file:
        return open(args.file, 'r')
    else:
        return sys.stdin

def _recursive_scan(args):
    scannable_files = []
    for root, dirs, files in os.walk("./"):
        if root.startswith('./.git'):
            continue
        for file in files:
            if file[0] != '.':
                scannable_files.append(path_join(root, file))

    for file in scannable_files:
        with open(file, 'r') as f:
            if detect_build_spec(f):
                if len(file) > 2 and file[0:2] == './':
                    file = file[2:]
                print(file)



def _main(args):
    stream = _get_stream(args)

    if args.detect_only:
        if detect_build_spec(stream):
            sys.exit(0)
        else:
            sys.exit(1)

    if args.recursive_scan:
        _recursive_scan(args)
        sys.exit(0)

    header = extract_build_spec(stream)
    if header == '':
        print("no build specification found", file=sys.stderr)
        sys.exit(1)

    if not args.clip:
        print(header, end='')
        sys.exit(0)
    else:
        if not args.file:
            print("--clip requires file input, not stdin", file=sys.stderr)
            sys.exit(1)
        stream.close()
        with open(args.file, 'w') as f:
            f.write(header)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Extract header including build spec from stream or file")
    parser.add_argument('file', nargs='?', help="The file to process. If not provided, stdin will be used.")
    parser.add_argument('-d', '--detect-only', action='store_true', help="only detect; errorlevel 0 if detected, 1 if not")
    parser.add_argument('--clip', action='store_true', help="Destructively clip the file to the header")
    parser.add_argument('-r', '--recursive-scan', action='store_true', help="Recursively find every file that has a build spec header")

    args = parser.parse_args()
    _main(args)
