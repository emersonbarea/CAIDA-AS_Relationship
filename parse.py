#!/usr/bin/python3

import json
import ipaddress


def parse(download_path, config_path):

    # get download config
    with open(config_path + 'download.json', 'r') as config_file:
        config = json.load(config_file)
    config_file.close()
    file = download_path + config['DOWNLOAD']['FILE']
    prefix_definition = config['PARSE']['PREFIX_DEFINITION']

    # create dictionary
    as_relationship = dict()
    topology = list()

    if prefix_definition == 'AUTOMATIC':

        # populate dictionary (peer1, peer2, prefix, peer1_IP, peer2_IP)
        count_prefix = 16777216
        with open(file) as file:
            for line in file:
                if not line.lstrip().startswith('#'):
                    as_relationship['peer1'] = line.split('|')[0]
                    as_relationship['peer2'] = line.split('|')[1]
                    as_relationship['prefix'] = count_prefix
                    as_relationship['peer1_IP'] = count_prefix + 1
                    as_relationship['peer2_IP'] = count_prefix + 254
                    count_prefix = count_prefix + 256
                    topology.append(as_relationship.copy())
            file.close()

        # create Mininet topology configuration (copy header, create elements and links, and create trailer)
        with open('topology.py', 'w') as file_to_write:

            # copy header from template
            with open(config_path + 'mininet_begin.template') as file_to_read:
                for line in file_to_read:
                    file_to_write.write(line)
            file_to_read.close()

            # create Mininet elements and links
            for peering in topology:
                file_to_write.write("AS%s = net.addDocker('AS%s', ip=None, dimage='alpine-quagga:latest')\n" % (peering['peer1'], peering['peer1']))
                file_to_write.write("AS%s = net.addDocker('AS%s', ip=None, dimage='alpine-quagga:latest')\n" % (peering['peer2'], peering['peer2']))
                file_to_write.write("net.addLink(AS%s, AS%s, intfName1='%s-%s', intfName2 = '%s-%s', params1={'ip':'%s/24'}, params2={'ip':'%s/24'})\n" % \
                      (peering['peer1'], peering['peer2'], peering['peer1'], peering['peer2'], peering['peer2'], peering['peer1'], \
                       str(ipaddress.ip_address(peering['peer1_IP'])), str(ipaddress.ip_address(peering['peer2_IP']))))

            # copy trailer from template
            with open(config_path + 'mininet_end.template') as file_to_read:
                for line in file_to_read:
                    file_to_write.write(line)
            file_to_read.close()
        file_to_write.close()


        # configure BGP



    elif prefix_definition == 'MANUAL':
        pass

    #for i in range(len(topology)):
    #    print(topology[i])



if __name__ == '__main__':
    download_path = './CAIDA_AS-Relationship_files/'
    config_path = './config/'
    parse(download_path, config_path)
