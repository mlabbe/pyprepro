# Pyprepro #

Barebones experimental program.

Create a ninja.build file from build edges.  For example, if foo.c
starts with:

    // || build-edge: ninja
    // || rule: grc
    // || in: grain/struct.gen grain/def.gr

This creates a ninja build edge line referencing rule type 'grc' that
targets foo.c as an output.  

The 'grc' program is intelligent enough to know to preserve this build
edge specification, and so the output file will rebuild successfully.


## Build-Edge Ninja Supported Keys ##

If a key isn't listed as supported here, it's passed on to ninja build verbatim.

### rule ###

The ninja build rule to invoke in order to generate this file.  The supported options are in 'build_rules' at the top of pyprepro.py.  Ultimately it would be nice to make this program build rule agnostic.

### in ###

One or more 'in' lines is required.  Each line contains one file that
is needed to build.

    // || in: message.tmpl
    // || in: vars.toml


### set ###

Given a line like:

    // || set: foo = bar
    
Create a variable %foo that is interpolated in 'in' lines.

It is possible to use variables to generate variables

    // || set: src_dir = ../src
    // || set: tmpl_dir = %src_dir/tmpl

Note that I wanted to use '$' instead of '%' but that conflicts with ninja build variables.
