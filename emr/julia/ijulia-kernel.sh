#!/bin/sh

# Install IJulia Kernel as the emr-notebook user
sudo -u emr-notebook JUPYTER=/emr/notebook-env/bin/jupyter /usr/local/bin/julia -e 'using Pkg; Pkg.add(["IJulia"])'