#!/usr/bin/python3

import pandas as pd
import json
import ipaddress
import time
import os
import shutil

class Parse(object):
    def __init__(self, config_path):
        # get config parameters
        with open(config_path + 'parse.json', 'r') as config_file:
            self.config = json.load(config_file)
        config_file.close()
        self.download_path = self.config['PARSE']['DOWNLOAD_PATH']
        self.file = self.download_path + self.config['PARSE']['FILE']
        self.output_dir = self.config['PARSE']['OUTPUT_DIR']
        self.container_type = self.config['PARSE']['CONTAINER']
        self.prefix_definition_type = self.config['PARSE']['PREFIX_DEFINITION']
        self.graph_dir = self.config['PARSE']['GRAPH_DIR']

    def df_from_file(self):
        # read CAIDA file to Pandas data frame
        self.df_from_file = pd.read_csv(self.file,
                                   sep='|',
                                   comment='#',
                                   header=None,
                                   skip_blank_lines=True,
                                   usecols=[0, 1, 2, 3],
                                   names=['as1', 'as2', 'pp_cp', 'got_from'],
                                   index_col=['as1'])
        #print(self.df_from_file)
        #       as1         as2        pp_cp        got_from
        #        1           2          -1             bgp
        #        1           3           0             mlp
        #   provider-as - customer-as = (pp_cp - -1)
        #   peer-as - peer-as = (pp_cp - 0)
        #
        #   AS Relationships, Customer Cones, and Validation = (got_from - bgp)
        #   AS relationships inferred from Ark traceroutes, and from multilateral peering = (got_from - mlp)

    def datafames(self):
        """
            populate peering dataframe (as1, as2, peer1_IP, peer2_IP, peer_mask, prefix1(prefix, mask, ...), prefix2(prefix, mask, ...))
        """
        print('    - parse')
        if self.prefix_definition_type == 'AUTOMATIC':  # ("AUTOMATIC" | "MANUAL")
            list_peer1_IP = list()
            list_peer2_IP = list()
            list_peer_mask = list()
            list_prefix = list()
            list_unique_as = list()
            count_prefix = 16777216
            for row in self.df_from_file.itertuples():
                list_unique_as.append(row[0])
                list_unique_as.append(row[1])
                list_peer1_IP.append(count_prefix + 1)
                list_peer2_IP.append(count_prefix + 254)
                list_peer_mask.append(24)
                list_prefix.append({'as': row[0], 'prefix': count_prefix, 'mask': 24})
                list_prefix.append({'as': row[1], 'prefix': count_prefix, 'mask': 24})
                count_prefix = count_prefix + 256
            self.list_unique_as = set(list_unique_as)  # create unique AS list
            self.df_from_file['peer1_IP'] = list_peer1_IP
            self.df_from_file['peer2_IP'] = list_peer2_IP
            self.df_from_file['peer_mask'] = list_peer_mask
            self.df_prefix1 = pd.DataFrame(list_prefix)
            self.df_prefix1.set_index('as', inplace=True)

            #print('quantidade de ASes únicos na topologia: ' + str(len(self.list_unique_as)))
            # qtd de ASes únicos na topologia: 64758

            #print(self.df_from_file)
            # as1        as2    pp_cp got_from   peer1_IP   peer2_IP  peer_mask
            # 1         3549      0      bgp     16777217   16777470         24
            # 1        11537      0      bgp     16777473   16777726         24
            # 1       133296      0      bgp     16777729   16777982         24
            # 2         6147     -1      bgp     16777985   16778238         24

            #print(self.df_prefix1)
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
        print('    - elements')
        if self.container_type == 'MININET': # ("MININET" | "DOCKER")
            for AS in self.list_unique_as:
                self.list_create_mininet_elements_commands.append("AS%s = net.addHost('AS%s', ip=None)" % (AS, AS))
        elif self.container_type == 'DOCKER': # ("MININET" | "DOCKER")
            for AS in self.list_unique_as:
                self.list_create_mininet_elements_commands.append("AS%s = net.addDocker('AS%s', ip=None, dimage='alpine-quagga:latest')" % (AS, AS))

        #print(self.list_create_mininet_elements_commands)
        #AS25970 = net.addHost('AS25970', ip=None)
        #AS265702 = net.addHost('AS265702', ip=None)

        # links
        print('    - links')
        self.list_create_mininet_links_commands = list()
        for row in self.df_from_file.itertuples():
            self.list_create_mininet_links_commands.append("net.addLink(AS%s, AS%s, intfName1='%s-%s', intfName2 = '%s-%s', params1={'ip':'%s/24'}, params2={'ip':'%s/24'})" % \
                                                           (row[0], row[1], row[0], row[1], row[1], row[0], str(ipaddress.ip_address(row[4])), str(ipaddress.ip_address(row[5]))))
        #print(self.list_create_mininet_links_commands)
        #net.addLink(AS397095, AS30168, intfName1='397095-30168', intfName2='30168-397095', params1={'ip': '9.44.173.1/24'}, params2={'ip': '9.44.173.254/24'})
        #net.addLink(AS397095, AS63343, intfName1='397095-63343', intfName2='63343-397095', params1={'ip': '9.44.174.1/24'}, params2={'ip': '9.44.174.254/24'})

    def quagga_commands(self):
        """
            Quagga configuration
        """
        # zebra and bgpd
        print('    - zebra and bgpd')
        list_create_zebra_interfaces = list()
        list_create_bgpd_neighbor = list()
        list_create_bgpd_prefix = list()
        list_routerid = list()
        for row in self.df_from_file.itertuples():
            # zebra
            list_create_zebra_interfaces.append({'as': row[0], 'command': 'interface %s-%s\n  ip address %s/%s\n\n' % (row[0], row[1], str(ipaddress.ip_address(row[4])), str(row[6]))})
            list_create_zebra_interfaces.append({'as': row[1], 'command': 'interface %s-%s\n  ip address %s/%s\n\n' % (row[1], row[0], str(ipaddress.ip_address(row[5])), str(row[6]))})
            # bgpd - router ID
            list_routerid.append({'as': row[0], 'router_ID': row[4]})
            list_routerid.append({'as': row[1], 'router_ID': row[5]})
            # bgpd - neighbor
            list_create_bgpd_neighbor.append({'as': row[0], 'command': '  neighbor %s remote-as %s\n' % (str(ipaddress.ip_address(row[5])), row[1])})
            list_create_bgpd_neighbor.append({'as': row[1], 'command': '  neighbor %s remote-as %s\n' % (str(ipaddress.ip_address(row[4])), row[0])})
            # bgpd - network (prefix)
            list_create_bgpd_prefix.append({'as': row[0], 'command': '  network %s\n' % (str(ipaddress.ip_network(str(ipaddress.ip_address(row[4])) + '/24', strict=False)))})
            list_create_bgpd_prefix.append({'as': row[1], 'command': '  network %s\n' % (str(ipaddress.ip_network(str(ipaddress.ip_address(row[5])) + '/24', strict=False)))})
        self.df_create_zebra_interfaces = pd.DataFrame(list_create_zebra_interfaces)
        self.df_create_zebra_interfaces.set_index('as', inplace=True)
        self.df_create_bgpd_neighbor = pd.DataFrame(list_create_bgpd_neighbor)
        self.df_create_bgpd_neighbor.set_index('as', inplace=True)
        self.df_create_bgpd_prefix = pd.DataFrame(list_create_bgpd_prefix)
        self.df_create_bgpd_prefix.set_index('as', inplace=True)

        self.df_create_routerid_temp = pd.DataFrame(list_routerid)
        self.df_create_routerid_temp.set_index('as', inplace=True)
        self.df_create_routerid = pd.DataFrame(
        self.df_create_routerid_temp.reset_index()[['as', 'router_ID']].groupby(by='as').min(axis=1))

        self.df_create_routerid = self.df_create_routerid.astype({'router_ID': str})
        for i, row in self.df_create_routerid.iterrows():
            self.df_create_routerid.at[i, 'router_ID'] = '  router id %s\n' % (str(ipaddress.ip_address(int(row[0]))))

        #print(self.df_from_file.reset_index()[['as1', 'peer1_IP']].groupby(by='as1').min(axis=1))

        #print(self.df_create_zebra_commands)
        # as            command
        # 1             interface 1-3549\n  ip address 1.0.0.1/24
        # 3549          interface 3549-1\n  ip address 1.0.0.254/24

        #print(self.df_create_bgpd_neighbor_commands)
        # as		command
        # 397285    	neighbor 9.44.178.254 remote-as 397268
        # 397268      	neighbor 9.44.178.1 remote-as 397285

        #print(self.df_create_bgpd_prefix_commands)
        # as	   command
        # 397187    network 9.44.177.0/24
        # 45974     network 9.44.177.0/24
        # 397285    network 9.44.178.0/24
        # 397268    network 9.44.178.0/24

        #print(self.df_create_routerid)
        #as         router_ID
        #397437     router id 4.122.238.254
        #397444     router id 3.135.39.254

    def write_to_file(self):
        """
            Write configuration to files
        """
        # erase previews configuration
        print('    - cleaning')
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)
        os.makedirs(self.output_dir + 'ASes')
        # Topology graph
        print('    - Topology graph')
        with open(self.output_dir + 'topology_graph_nodes.output', 'w') as file_graph_nodes:
            for AS in self.list_unique_as:
                file_graph_nodes.write('%s\n' % (AS))
        file_graph_nodes.close()
        with open(self.output_dir + 'topology_graph_edges.output', 'w') as file_graph_edges:
            for row in self.df_from_file.itertuples():
                file_graph_edges.write('%s, %s\n' % (row[0], row[1]))
        file_graph_edges.close()
        # Mininet
        print('    - Mininet')
        with open(self.output_dir + 'topology.py', 'w') as file_topology:
            print('        - header')
            with open(config_path + 'mininet_begin.template', 'r') as file_to_read:
                file_topology.write(file_to_read.read())
            file_to_read.close()
            print('        - elements')
            for mininet_element in self.list_create_mininet_elements_commands:
                file_topology.write(mininet_element + '\n')
            print('        - links')
            for mininet_link in self.list_create_mininet_links_commands:
                file_topology.write(mininet_link + '\n')
            print('        - end')
            with open(config_path + 'mininet_end.template', 'r') as file_to_read:
                file_topology.write(file_to_read.read())
            file_to_read.close()
        file_topology.close()

        print('    - ASes config directory')
        for AS in self.list_unique_as:
            os.makedirs(self.output_dir + 'ASes/' + str(AS))

        # zebra.conf
        print('    - zebra.conf and bgpd.conf')
        # zebra.conf and bgpd.conf header
        for AS in self.list_unique_as:
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

    def graph(self):
        if os.path.exists(self.graph_dir + 'data.js'):
            os.remove(self.graph_dir + 'data.js')

        print('    - nodes')
        with open(self.graph_dir + 'nodes.js', 'w') as write_to_file:
            write_to_file.write('var nodes = new vis.DataSet([\n')
            for AS in self.list_unique_as:
                write_to_file.write('{id: %s, label: "%s"},\n' % (AS, AS))
            write_to_file.write(']);')
        write_to_file.close()
        print('    - edges')
        with open(self.graph_dir + 'edges.js', 'w') as write_to_file:
            write_to_file.write('var edges = new vis.DataSet([\n')
            for row in self.df_from_file.itertuples():
                write_to_file.write('{from: %s, to: %s},\n' % (row[0], row[1]))
            write_to_file.write(']);')
        write_to_file.close()



if __name__ == '__main__':
    start = time.time()
    config_path = './config/'
    parse = Parse(config_path)
    print('Parse')
    parse.df_from_file()
    t1 = time.time()
    print(t1 - start)
    parse.datafames()
    t2 = time.time()
    print(t2 - t1)
    #parse.mininet_commands()
    t3 = time.time()
    print(t3 - t2)
    #parse.quagga_commands()
    t4 = time.time()
    print(t4 - t3)
    print('Write to file')
    #parse.write_to_file()
    t5 = time.time()
    print(t5 - t4)
    print('Graph')
    parse.graph()
    t6 = time.time()
    print(t6 - t5)




    end = time.time()
    print('Total: ' + str(end - start))