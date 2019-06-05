#!/bin/bash

if [ "$1" == "--help" ] || [ "$1" == "-h" ]
then
	printf "\nInvoke without any parameter for complete and unguided installation of MiniSecBGP and its dependencies.\n\n"
	exit 0
fi

if [ "$1" != "" ]
then
	printf "\nWrong parameter '$1'.\nInvoke without any parameter for complete and unguided installation of MiniSecBGP and its dependencies.\n\n"
	exit 0
fi

function welcome() {
	printf "\nMiniSecBGP 1.0 installer\n
        This program install MiniSecBGP 1.0 and all requirements to the home directory of '$USER' user on Ubuntu Server 18.04 LTS
        It will automatically remove existing '$USER' user and erase all data in '/home/$USER' directory
	It will change network configuration to permit cluster nodes network communication
	Execute 'install.sh -h' or 'install.sh --help' to help\n

	This installer will now configure:
	    - NIC 1 IP = dhcp client
	    - NIC 2 IP = 192.168.254.X/24
	    - hostname = nodeX
	    - erase and recreate '$USER' user and home directory (username = '$USER' | password = '$USER')
	    - configure user '$USER' in sudoers
	    - configure SSH service to permit tunnels

	This installer will now install:
           -Mininet 2.2.1rc1
           -Containernet 2.2.1
     	   -Metis 5.1
	   -Pyro 4
           -MaxiNet 1.2

       Obs.: thank you MaxiNet install program (https://raw.githubusercontent.com/MaxiNet/MaxiNet/master/installer.sh)\n\n"

	read -n1 -r -p "Press ANY key to continue or CTRL+C to abort." abort
}

function qtd_hosts() {
	read -n1 -r -p "How many nodes are there in the cluster? (only number. Ex.: 3): " var_qtd_hosts
    	re='^[0-9]+$'
	if ! [[ $var_qtd_hosts =~ $re ]]
	then
        	printf "\e[1;31m%-6s\e[m\n" "error: only numbers"
        	qtd_hosts;
    	fi
}

function prereq() {
	printf "\n\n\e[1;33m%-6s%s\e[m\n\n" "Install O.S. requeriments"
	sudo apt update
	sudo apt upgrade -y
	sudo apt install python3 python3-pip ansible cmake whois -y
	sudo pip3 install pandas
	sudo apt autoremove -y
}

function config() {
        printf "\n\e[1;33m%-6s%s\e[m\n\n" "Configuring network, hostname, user and SSH"

        printf "\n\e[1;33m%-6s\e[m\n" "-- network"
        sudo apt autoremove netplan netplan.io nplan -y &> /dev/null
        sudo sed -i -- 's/GRUB_CMDLINE_LINUX=""/GRUB_CMDLINE_LINUX="net.ifnames=0 biosdevname=0"/g' /etc/default/grub
        sudo grub-mkconfig -o /boot/grub/grub.cfg
        printf '%s\n' $'auto lo\niface lo inet loopback\n\nallow-hotplug eth0\niface eth0 inet dhcp' | sudo tee /etc/network/interfaces

	printf "\n\e[1;33m%-6s\e[m\n" "-- hosts"
	sudo hostnamectl set-hostname localhost
	printf "%s\n" "127.0.0.1 localhost.localdomain localhost" | sudo tee /etc/hosts
    	for ((i=1; i<=$var_qtd_hosts; i++)); do
        	printf '%s\n' "192.168.254.$i    node$i" | sudo tee --append /etc/hosts; done

        printf "\n\e[1;33m%-6s\e[m\n" "-- user '$USER'"
	sudo userdel -r $USER &> /dev/null
   	sudo useradd -m -p $(mkpasswd -m sha-512 -S saltsalt -s <<< $USER) -s /bin/bash $USER
        printf "%s\n" "$USER     ALL=NOPASSWD: ALL" | sudo tee --append /etc/sudoers
	sudo -u $USER cp -r ../MiniSecBGP/ $HOME_DIR

	printf "\n\e[1;33m%-6s\e[m\n" "-- SSH"
	sudo sed -i -- 's/#PermitTunnel no/PermitTunnel yes/g' /etc/ssh/sshd_config
    	sudo -u $USER ssh-keygen -t rsa -N "" -f $HOME_DIR/.ssh/id_rsa
    	for (( c=1; c<=$var_qtd_hosts; c++ )); do
        	sudo -u $USER cat $HOME_DIR/.ssh/id_rsa.pub | \
        	sudo -u $USER tee --append $HOME_DIR/.ssh/authorized_keys; done
    	for i in $(sudo -u $USER cat -n $HOME_DIR/.ssh/authorized_keys | awk '{print $1}'); do
        	sudo -u $USER sed -Ei "${i}s/@.*/@node$i/" $HOME_DIR/.ssh/authorized_keys; done
    	sudo -u $USER cat $HOME_DIR/.ssh/authorized_keys
    	sudo -u $USER chmod 755 $HOME_DIR/.ssh/authorized_keys
    	printf '%s\n' $'Host *\nStrictHostKeyChecking no' | \
        	sudo -u $USER tee --append $HOME_DIR/.ssh/config
    	sudo -u $USER chmod 400 $HOME_DIR/.ssh/config

	printf "\n\e[1;33m%-6s\e[m\n" "-- cluster nodes"
    	sudo -u $USER rm -rf $INSTALL_DIR/nodes &> /dev/null
    	sudo -u $USER mkdir -p $INSTALL_DIR/nodes
    	for ((i=1; i<=$var_qtd_hosts; i++)); do
        	sudo -u $USER cp $INSTALL_DIR/scripts/nodes/template_node.sh $INSTALL_DIR/nodes/node$i.sh;
	        sudo -u $USER sed -i -- 's/<node_number>/'$i'/g' $INSTALL_DIR/nodes/node$i.sh;
        	sudo -u $USER chmod 755 $INSTALL_DIR/nodes/node$i.sh; done
}

function Mininet() {
	printf "\n\e[1;33m%-6s%s\e[m\n\n" "Install Mininet"
	cd $INSTALL_DIR
	sudo rm -rf openflow &> /dev/null
	sudo rm -rf loxigen &> /dev/null
	sudo rm -rf pox &> /dev/null
	sudo rm -rf oftest &> /dev/null
	sudo rm -rf oflops &> /dev/null
	sudo rm -rf ryu &> /dev/null
	sudo rm -rf mininet &> /dev/null
	sudo -u $USER git clone git://github.com/mininet/mininet
	cd mininet
	sudo -u $USER git checkout -b 2.2.1rc1 2.2.1rc1
	cd util/
	sudo -u $USER ./install.sh
	if [ "$?" != "0" ]
	then
		sudo -u $USER ./install.sh
	fi
}

function Containernet() {
	printf "\n\e[1;33m%-6s%s\e[m\n\n" "Install Containernet"
	cd $INSTALL_DIR
	sudo grep "localhost ansible_connection=local" /etc/ansible/hosts >/dev/null
	if [ $? -ne 0 ]; 
	then
		sudo echo "localhost ansible_connection=local" | sudo tee -a /etc/ansible/hosts
  	fi
	sudo rm -rf containernet &> /dev/null
	sudo rm -rf oflops &> /dev/null
	sudo rm -rf oftest &> /dev/null
	sudo rm -rf openflow &> /dev/null
	sudo rm -rf pox &> /dev/null
	sudo -u $USER git clone https://github.com/containernet/containernet
	cd containernet/ansible
	sudo ansible-playbook install.yml
}

function Metis() {
	printf "\n\e[1;33m%-6s%s\e[m\n\n" "Install Metis"
	cd $INSTALL_DIR
	#sudo -u $USER wget http://glaros.dtc.umn.edu/gkhome/fetch/sw/metis/metis-5.1.0.tar.gz
	sudo -u $USER wget http://192.168.56.1/metis-5.1.0.tar.gz
	sudo -u $USER tar -xzf metis-5.1.0.tar.gz
	sudo -u $USER rm metis-5.1.0.tar.gz
	cd metis-5.1.0
	sudo -u $USER make config
	sudo -u $USER make
	sudo make install
}

function Pyro4() {
	printf "\n\e[1;33m%-6s%s\e[m\n\n" "Install Pyro4"
        sudo pip3 install Pyro4
}

function MaxiNet() {
	printf "\n\e[1;33m%-6s%s\e[m\n\n" "Install MaxiNet"
	cd $INSTALL_DIR 
	sudo rm -rf MaxiNet &> /dev/null
	sudo -u $USER git clone git://github.com/MaxiNet/MaxiNet.git
	cd MaxiNet
	sudo -u $USER git checkout v1.2
	sudo make install
	printf "\n\e[1;33m%-6s\e[m\n" "-- cluster nodes"
	sudo cp $INSTALL_DIR/MaxiNet/share/MaxiNet-cfg-sample /etc/MaxiNet.cfg
	sudo sed -i -- "s/password = HalloWelt/password = $USER/g" /etc/MaxiNet.cfg
	sudo sed -i -- "s/controller = 192.168.123.1:6633/controller = 192.168.254.1:6633/g" /etc/MaxiNet.cfg
	sudo sed -i -- "s/logLevel = INFO/logLevel = ERROR/g" /etc/MaxiNet.cfg
	sudo sed -i -- "s/sshuser = root/sshuser = $USER/g" /etc/MaxiNet.cfg
	sudo sed -i -- "s/usesudo = False/usesudo = True/g" /etc/MaxiNet.cfg
	sudo sed -i -- "s/ip = 192.168.123.1/ip = 192.168.254.1/g" /etc/MaxiNet.cfg
	sudo sed -i -- 19,'$d' /etc/MaxiNet.cfg
	for ((i=1; i<=$var_qtd_hosts; i++)); do 
        	printf "[node$i] \nip = 192.168.254.$i \nshare = 1\n\n" | sudo tee --append /etc/MaxiNet.cfg; done
	sudo cat /etc/MaxiNet.cfg 
}

main() {
	USER="minisecbgp"
	HOME_DIR="/home/$USER"
	INSTALL_DIR="$HOME_DIR/MiniSecBGP"
	welcome;
	qtd_hosts;
	prereq;
	config;
	Mininet;
	Containernet;
	Metis;
	Pyro4;
	MaxiNet;
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
