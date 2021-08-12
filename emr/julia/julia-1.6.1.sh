#!/bin/sh
curl -OL https://julialang-s3.julialang.org/bin/linux/x64/1.6/julia-1.6.1-linux-x86_64.tar.gz

sudo mkdir -p /opt; sudo tar xf julia-1.6.1-linux-x86_64.tar.gz --directory /opt

sudo ln -s /opt/julia-1.6.1/bin/julia /usr/local/bin/julia
