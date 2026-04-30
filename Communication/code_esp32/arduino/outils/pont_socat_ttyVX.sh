#!/bin/bash

gnome-terminal --tab -- bash -c "socat -d -d pty,raw,echo=0,link=/tmp/ttyV0   pty,raw,echo=0,link=/tmp/ttyV1"
