#!/usr/bin/python3

import json
import urllib.request
import shutil
import bz2
import os


def download(config_path):

    # get download config
    with open(config_path + 'download.json', 'r') as config_file:
        config = json.load(config_file)
    config_file.close()
    url = config['DOWNLOAD']['URL']
    serial = config['DOWNLOAD']['SERIAL']
    download_file = config['DOWNLOAD']['DOWNLOAD_FILE']
    download_path = config['DOWNLOAD']['DOWNLOAD_PATH']

    # download CAIDA AS-Relationship file
    output_zip_file = download_path + download_file
    output_file = download_path + download_file[:-4]

    # create download directory
    if os.path.exists(download_path):
        shutil.rmtree(download_path)
    os.makedirs(download_path)

    with urllib.request.urlopen(url + serial + download_file) as response, \
            open(output_zip_file, 'wb') as out_file:
        shutil.copyfileobj(response, out_file)

    # decompress CAIDA AS-Relationship file
    file = bz2.open(output_zip_file, 'rt')
    data = file.read()
    file = open(output_file, 'w+')
    file.write(data)
    file.close()

    # erase bz2 file
    os.remove(output_zip_file)


if __name__ == '__main__':
    config_path = './config/'
    download(config_path)