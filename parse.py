#!/usr/bin/python3

import pandas as pd
import json
import ipaddress
import time
import os
import shutil


class Parse(object):
    def __init__(self, config_path):
        """
            get config parameters
        """
        
        # define text color
        self.green = '\x1b[33;92m'
        self.default = '\x1b[0m'

        with open(config_path + 'parse.json', 'r') as config_file:
            self.config = json.load(config_file)
        config_file.close()
        self.download_path = self.config['PARSE']['DOWNLOAD_PATH']
        self.file = self.download_path + self.config['PARSE']['FILE']
        self.output_dir = self.config['PARSE']['OUTPUT_DIR']
        self.topology_length = self.config['PARSE']['TOPOLOGY_LENGTH']
        self.container_type = self.config['PARSE']['CONTAINER']
        self.prefix_definition_type = self.config['PARSE']['PREFIX_DEFINITION']
        self.graph_dir = self.config['PARSE']['GRAPH_DIR']

        print('\nParameters:\n \
                - Download path: %s %s %s\n \
                - Download file name: %s %s %s\n \
                - Output configuration directory: %s %s %s\n \
                - Topology length ("FULL", "STUB"): %s %s %s\n \
                - Container type ("MININET", "DOCKER"): %s %s %s\n \
                - Prefix IP definition type ("AUTOMATIC", "MANUAL"): %s %s %s\n \
                - Output graph directory: %s %s %s\n' % (\
                    self.green, self.download_path, self.default, \
                    self.green, self.file, self.default, \
                    self.green, self.output_dir, self.default, \
                    self.green, self.topology_length, self.default, \
                    self.green, self.container_type, self.default, \
                    self.green, self.prefix_definition_type, self.default, \
                    self.green, self.graph_dir, self.default))

    def df_from_file(self):
        """
            read CAIDA file to Pandas data frame
        """
        self.df_from_file = pd.read_csv(self.file,
                                        sep='|',
                                        comment='#',
                                        header=None,
                                        skip_blank_lines=True,
                                        usecols=[0, 1, 2, 3],
                                        names=['AS1', 'AS2', 'pp_cp', 'got_from'],
                                        index_col=['AS1'])
        # print(self.df_from_file)
        #       as1         as2        pp_cp        got_from
        #        1           2          -1             bgp
        #        1           3           0             mlp
        #   provider-as - customer-as = (pp_cp - -1)
        #   peer-as - peer-as = (pp_cp - 0)
        #
        #   AS Relationships, Customer Cones, and Validation = (got_from - bgp)
        #   AS relationships inferred from Ark traceroutes, and from multilateral peering = (got_from - mlp)

    def data_frames(self):
        """
            populate peering dataframe (as1, as2, peer1_IP, peer2_IP, peer_mask, prefix1(prefix, mask, ...), prefix2(prefix, mask, ...))
        """
        sr_all_ases = pd.concat([self.df_from_file.reset_index()['AS1'], self.df_from_file['AS2']], ignore_index=True)
        sr_stub = sr_all_ases.drop_duplicates(keep=False)                                       # save only stub ASes
        sr_unique_as = sr_all_ases.drop_duplicates(keep='first')                                # save all unique ASes (stub and not stub)

        print('Number of ASes: %s %s %s' % (self.green, len(sr_unique_as), self.default))
        print('Number of stub ASes: %s %s %s (Number of ASes not stub: %s %s %s)\n' % (\
                self.green, len(sr_stub), self.default, self.green, len(sr_unique_as) - len(sr_stub), self.default))

        if self.topology_length == 'STUB':                                                      # ("STUB" | "FULL")
            self.sr_unique_as = pd.concat([sr_unique_as, sr_stub]).drop_duplicates(keep=False)  # save all ASes removing stub ASes

        elif self.topology_length == 'FULL':                                                    # ("STUB" | "FULL")
            self.sr_unique_as = sr_unique_as

        if self.prefix_definition_type == 'AUTOMATIC':  # ("AUTOMATIC" | "MANUAL")
            list_peer1_ip = list()
            list_peer2_ip = list()
            list_peer_mask = list()
            list_prefix = list()
            count_prefix = 16777216
            for row in self.df_from_file.itertuples():
                list_peer1_ip.append(count_prefix + 1)
                list_peer2_ip.append(count_prefix + 254)
                list_peer_mask.append(24)
                list_prefix.append({'AS': row[0], 'prefix': count_prefix, 'mask': 24})
                list_prefix.append({'AS': row[1], 'prefix': count_prefix, 'mask': 24})
                count_prefix = count_prefix + 256
            self.df_from_file['peer1_IP'] = list_peer1_ip
            self.df_from_file['peer2_IP'] = list_peer2_ip
            self.df_from_file['peer_mask'] = list_peer_mask
            self.df_prefix1 = pd.DataFrame(list_prefix)
            self.df_prefix1.set_index('AS', inplace=True)

            # print(self.df_from_file)
            # as1        as2    pp_cp got_from   peer1_IP   peer2_IP  peer_mask
            # 1         3549      0      bgp     16777217   16777470         24
            # 1        11537      0      bgp     16777473   16777726         24
            # 1       133296      0      bgp     16777729   16777982         24
            # 2         6147     -1      bgp     16777985   16778238         24

            # print(self.df_prefix1)
            # as      mask     prefix
            # 1         24   16777216
            # 3549      24   16777216

        elif self.prefix_definition_type == 'MANUAL':  # ("AUTOMATIC" | "MANUAL")
            pass

    def mininet_commands(self):
        """
            Mininet elements and links configuration
        """
        # elements
        self.list_create_mininet_elements_commands = list()
        if self.container_type == 'MININET':  # ("MININET" | "DOCKER")
            for AS in self.sr_unique_as:
                self.list_create_mininet_elements_commands.append("AS%s = net.addHost('AS%s', ip=None)" % (AS, AS))
        elif self.container_type == 'DOCKER':  # ("MININET" | "DOCKER")
            for AS in self.sr_unique_as:
                self.list_create_mininet_elements_commands.append(
                    "AS%s = net.addDocker('AS%s', ip=None, dimage='alpine-quagga:latest')" % (AS, AS))

        # print(self.list_create_mininet_elements_commands)
        # AS25970 = net.addHost('AS25970', ip=None)
        # AS265702 = net.addHost('AS265702', ip=None)

        # links
        self.list_create_mininet_links_commands = list()
        for row in self.df_from_file.itertuples():
            if row[0] in self.sr_unique_as.values and row[1] in self.sr_unique_as.values:   # do not link stub ASes if necessary
                self.list_create_mininet_links_commands.append(
                    "net.addLink(AS%s, AS%s, intfName1='%s-%s', intfName2 = '%s-%s', params1={'ip':'%s/24'}, params2={'ip':'%s/24'})" % \
                    (row[0], row[1], row[0], row[1], row[1], row[0], str(ipaddress.ip_address(row[4])),
                    str(ipaddress.ip_address(row[5]))))

        # print(self.list_create_mininet_links_commands)
        # net.addLink(AS1, AS2, intfName1='1-2', intfName2='2-1', params1={'ip': '1.1.1.1/24'}, params2={'ip': '1.1.1.254/24'})
        # net.addLink(AS2, AS3, intfName1='2-3', intfName2='3-2', params1={'ip': '1.1.2.1/24'}, params2={'ip': '1.1.2.254/24'})

    def quagga_commands(self):
        """
            Quagga configuration
        """
        # zebra and bgpd
        list_create_zebra_interfaces = list()
        list_create_bgpd_neighbor = list()
        list_create_bgpd_prefix = list()
        list_routerid = list()
        for row in self.df_from_file.itertuples():
            if row[0] in self.sr_unique_as.values and row[1] in self.sr_unique_as.values:   # do not link stub ASes if necessary    
                # zebra
                list_create_zebra_interfaces.append({'AS': row[0], 'command': 'interface %s-%s\n  ip address %s/%s\n\n' % (
                row[0], row[1], str(ipaddress.ip_address(row[4])), str(row[6]))})
                list_create_zebra_interfaces.append({'AS': row[1], 'command': 'interface %s-%s\n  ip address %s/%s\n\n' % (
                row[1], row[0], str(ipaddress.ip_address(row[5])), str(row[6]))})
                # bgpd - router ID
                list_routerid.append({'AS': row[0], 'router_ID': row[4]})
                list_routerid.append({'AS': row[1], 'router_ID': row[5]})
                # bgpd - neighbor
                list_create_bgpd_neighbor.append(
                {'AS': row[0], 'command': '  neighbor %s remote-as %s\n' % (str(ipaddress.ip_address(row[5])), row[1])})
                list_create_bgpd_neighbor.append(
                {'AS': row[1], 'command': '  neighbor %s remote-as %s\n' % (str(ipaddress.ip_address(row[4])), row[0])})
                # bgpd - network (prefix)
                list_create_bgpd_prefix.append({'AS': row[0], 'command': '  network %s\n' % (
                    str(ipaddress.ip_network(str(ipaddress.ip_address(row[4])) + '/24', strict=False)))})
                list_create_bgpd_prefix.append({'AS': row[1], 'command': '  network %s\n' % (
                    str(ipaddress.ip_network(str(ipaddress.ip_address(row[5])) + '/24', strict=False)))})

            # create BGP "network" command with stub AS prefix in root AS
            elif row[0] not in self.sr_unique_as.values and row[1] in self.sr_unique_as.values: 
                list_create_bgpd_prefix.append({'AS': row[1], 'command': '  network %s\n' % (
                     str(ipaddress.ip_network(str(ipaddress.ip_address(row[4])) + '/24', strict=False)))})
            elif row[0] in self.sr_unique_as.values and row[1] not in self.sr_unique_as.values:
                list_create_bgpd_prefix.append({'AS': row[0], 'command': '  network %s\n' % (
                     str(ipaddress.ip_network(str(ipaddress.ip_address(row[5])) + '/24', strict=False)))})
        
        self.df_create_zebra_interfaces = pd.DataFrame(list_create_zebra_interfaces)
        self.df_create_zebra_interfaces.set_index('AS', inplace=True)
        self.df_create_bgpd_neighbor = pd.DataFrame(list_create_bgpd_neighbor)
        self.df_create_bgpd_neighbor.set_index('AS', inplace=True)
        self.df_create_bgpd_prefix = pd.DataFrame(list_create_bgpd_prefix)
        self.df_create_bgpd_prefix.set_index('AS', inplace=True)

        # uses the smallest router-id in BGP
        self.df_create_routerid_temp = pd.DataFrame(list_routerid)
        self.df_create_routerid_temp.set_index('AS', inplace=True)
        self.df_create_routerid = pd.DataFrame(
            self.df_create_routerid_temp.reset_index()[['AS', 'router_ID']].groupby(by='AS').min())

        self.df_create_routerid = self.df_create_routerid.astype({'router_ID': str})
        for i, row in self.df_create_routerid.iterrows():
            self.df_create_routerid.at[i, 'router_ID'] = '  router id %s\n' % (str(ipaddress.ip_address(int(row[0]))))

        # print(self.df_create_zebra_interfaces)
        # AS            command
        # 1             interface 1-3549\n  ip address 1.0.0.1/24
        # 3549          interface 3549-1\n  ip address 1.0.0.254/24

        # print(self.df_create_bgpd_neighbor)
        # AS		command
        # 397285    	neighbor 9.44.178.254 remote-as 397268
        # 397268      	neighbor 9.44.178.1 remote-as 397285

        # print(self.df_create_bgpd_prefix)
        # AS	   command
        # 397187    network 9.44.177.0/24
        # 45974     network 9.44.177.0/24
        # 397285    network 9.44.178.0/24
        # 397268    network 9.44.178.0/24

        # print(self.df_create_routerid)
        # AS         router_ID
        # 397437     router id 4.122.238.254
        # 397444     router id 3.135.39.254

    def write_to_file(self):
        """
            Write configuration and Graph to files
        """
        # erase previews configuration
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)
        os.makedirs(self.output_dir + 'ASes')
        if os.path.exists(self.graph_dir):
            shutil.rmtree(self.graph_dir)
        os.makedirs(self.graph_dir)

        # Topology graph
        with open(self.graph_dir + 'nodes.js', 'w') as write_to_file:
            write_to_file.write('var nodes = new vis.DataSet([\n')
            for AS in self.sr_unique_as:
                write_to_file.write('{id: %s, label: "%s"},\n' % (AS, AS))
            write_to_file.write(']);')
        write_to_file.close()
        
        with open(self.graph_dir + 'edges.js', 'w') as write_to_file:
            write_to_file.write('var edges = new vis.DataSet([\n')
            for row in self.df_from_file.itertuples():
                if row[0] in self.sr_unique_as.values and row[1] in self.sr_unique_as.values:   # do not link stub ASes if necessary
                    color = 'red' if row[2] == 0 else 'black'
                    write_to_file.write('{from: %s, to: %s, color:{color:"%s"}},\n' % (row[0], row[1], color))
            write_to_file.write(']);')
        write_to_file.close()

        # Mininet
        with open(self.output_dir + 'topology.py', 'w') as file_topology:
            with open(config_path + 'mininet_begin.template', 'r') as file_to_read:
                file_topology.write(file_to_read.read())
            file_to_read.close()
            for mininet_element in self.list_create_mininet_elements_commands:
                file_topology.write(mininet_element + '\n')
            for mininet_link in self.list_create_mininet_links_commands:
                file_topology.write(mininet_link + '\n')
            with open(config_path + 'mininet_end.template', 'r') as file_to_read:
                file_topology.write(file_to_read.read())
            file_to_read.close()
        file_topology.close()

        for AS in self.sr_unique_as:
            os.makedirs(self.output_dir + 'ASes/' + str(AS))

        # zebra.conf and bgpd.conf header
        for AS in self.sr_unique_as:
            with open(self.output_dir + 'ASes/' + str(AS) + '/zebra.conf', 'w') as file_zebra:
                with open(config_path + 'zebra.conf.template', 'r') as file_to_read_zebra:
                    file_zebra.write(file_to_read_zebra.read().replace('*AS*', str(AS)))
                file_to_read_zebra.close()
            with open(self.output_dir + 'ASes/' + str(AS) + '/bgpd.conf', 'w') as file_bgpd:
                with open(config_path + 'bgpd.conf.template', 'r') as file_to_read_bgpd:
                    file_bgpd.write(file_to_read_bgpd.read().replace('*AS*', str(AS)))
                file_to_read_bgpd.close()
            file_zebra.close()
            file_bgpd.close()
        # zebra.conf interfaces
        for row in self.df_create_zebra_interfaces.itertuples():
            with open(self.output_dir + 'ASes/' + str(row[0]) + '/zebra.conf', 'a') as file_zebra:
                file_zebra.write(row[1])
            file_zebra.close()
        # bgpd.conf router ID
        for row in self.df_create_routerid.itertuples():
            with open(self.output_dir + 'ASes/' + str(row[0]) + '/bgpd.conf', 'a') as file_bgpd:
                file_bgpd.write(row[1])
            file_bgpd.close()
        # bgpd.conf neighbor
        for row in self.df_create_bgpd_neighbor.itertuples():
            with open(self.output_dir + 'ASes/' + str(row[0]) + '/bgpd.conf', 'a') as file_bgpd:
                file_bgpd.write(row[1])
            file_bgpd.close()
        # bgpd.conf prefix
        for row in self.df_create_bgpd_prefix.itertuples():
            with open(self.output_dir + 'ASes/' + str(row[0]) + '/bgpd.conf', 'a') as file_bgpd:
                file_bgpd.write(row[1])
            file_bgpd.close()


if __name__ == '__main__':
    start = time.time()
    config_path = './config/'
    parse = Parse(config_path)
    parse.df_from_file()
    t1 = time.time()
    parse.data_frames()
    t2 = time.time()
    print('time - Populating peering dataframe (as1, as2, peer1_IP, peer2_IP, peer_mask, prefix1, prefix2): %s\n' % (t2 - t1))
    parse.mininet_commands()
    t3 = time.time()
    print('time - Creating Mininet commands: %s\n' % (t3 - t2))
    parse.quagga_commands()
    t4 = time.time()
    print('time - Creating Quagga commands: %s\n' % (t4 - t3))
    parse.write_to_file()
    t5 = time.time()
    print('time - Writing files configuration: %s\n' % (t5 - t4))
    end = time.time()
    print('Total execution time: %s\n' % (end - start))
