#!/bin/bash

# coproc requires bash 4.x
coproc python connmux.py noc.pirxnet.pl 80 client 2>./client.log
python connmux.py 0.0.0.0 9999 server <&${COPROC[0]} >&${COPROC[1]} 2>./server.log
