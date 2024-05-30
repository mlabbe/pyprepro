# Pyprepro #

Barebones experimental program.

Create a ninja.build file from build edges.  For example, if foo.c
starts with:

    // -|- build-edge: ninja-rule
    // -|- rule: grc
    // -|- in: grain/struct.gen grain/def.gr

This creates a ninja build edge line referencing rule type 'grc' that
targets foo.c as an output.  

The 'grc' program is intelligent enough to know to preserve this build
edge specification, and so the output file will rebuild successfully.
