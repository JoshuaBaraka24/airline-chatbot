#!/usr/bin/env bash
# Prepares a fresh Ubuntu 24.04 server (such as an Azure VM) to run the system.
# Safe to run again: it skips anything already done.
set -euo pipefail

if ! command -v docker > /dev/null; then
    echo "Installing Docker"
    sudo apt-get update -q
    sudo apt-get install -y -q docker.io docker-compose-v2
    sudo systemctl enable --now docker
fi

# The language model needs about 3 GB of memory while it loads; on a 4 GB
# server a swap file stops it from being killed for lack of memory
if [ ! -f /swapfile ]; then
    echo "Adding a 4 GB swap file"
    sudo fallocate -l 4G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile > /dev/null
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab > /dev/null
fi
