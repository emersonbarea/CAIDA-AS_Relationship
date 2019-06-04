#!/bin/bash

sudo apt update
sudo apt upgrade -y
sudo apt install python3 python3-pip -y
sudo pip3 install pandas

sudo apt autoremove -y

