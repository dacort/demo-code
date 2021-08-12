#!/bin/sh

curl -OL https://julialang-s3.julialang.org/bin/linux/x64/1.6/julia-1.6.1-linux-x86_64.tar.gz

sudo mkdir -p /opt; sudo tar xf julia-1.6.1-linux-x86_64.tar.gz --directory /opt

sudo ln -s /opt/julia-1.6.1/bin/julia /usr/local/bin/julia


cat > /tmp/setup.sh << EOF
/bin/sh

while ! grep -q emr-notebook /etc/passwd; do sleep 10; done;

sleep 10

sudo -u emr-notebook JUPYTER=/emr/notebook-env/bin/jupyter /usr/local/bin/julia -e 'using Pkg; Pkg.add(["IJulia"])'

EOF

chmod +x /tmp/setup.sh

nohup /tmp/setup.sh 2>&1 &
