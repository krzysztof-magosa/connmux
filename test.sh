#!/bin/bash

# coproc requires bash 4.x
coproc python main.py noc.pirxnet.pl 80 client
python main.py 0.0.0.0 9999 server <&${COPROC[0]} >&${COPROC[1]}
