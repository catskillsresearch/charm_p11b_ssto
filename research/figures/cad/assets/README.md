# Reusable CAD assets

This directory holds source assets that can be redistributed with this project.
Every binary must be listed in `manifest.json` with its source URL, reuse terms,
checksum, and `assembly.json` parts it supports.

## Selection policy

Accept only public-domain, CC0, or explicitly reusable government-source files.
Do not add marketplace "royalty-free" files, BlenderKit royalty-free assets, or
assets requiring a login/subscription: they may be usable in a render, but they
are not suitable for a repository containing editable Blender scenes.

## Current asset

`nasa/crew_lock_bag.glb` is the NASA Crew Lock Bag model. It is used as a
stowage/food-pouch proxy in the Blender crew-capsule cutaway. Review NASA's
Images and Media Usage Guidelines before changing its use or distributing a
derivative.

## Deliberately project-authored geometry

Seats, pressure hatches, WCS, ECLSS racks, and O2/N2 tank arrangements remain
project geometry. They determine interfaces, fit, access, and clearances, so a
generic downloaded model must not silently redefine the packaging model.
