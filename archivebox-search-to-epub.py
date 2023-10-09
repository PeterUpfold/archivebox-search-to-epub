#!/usr/bin/env python3
#
# archivebox-search-to-epub
#
# Uses `ebook-convert` to convert Readability version of an ArchiveBox item for consuming
# articles offline in ePub format.

import json
import subprocess
import sys
import sqlite3
import re
import os
from datetime import datetime

with open(os.path.join(os.path.dirname(__file__), 'volatile/config.json'), 'r') as json_file:
    config = json.load(json_file)

# must provide the search query as the first argument
if len(sys.argv) < 2:
    print('Please provide the search query as the first argument.', file=sys.stderr)
    sys.exit(1)

# check config
required_config_keys = [
    'archivebox_root',
    'output_dir',
    'invoke_node_cmdline',
    'embed_images_tool',
    'ebook_convert_cmdline',
    'max_image_size',
    'output_profile'
]
for required_key in required_config_keys:    
    if not required_key in config.keys():
        print(f'{required_key} is not configured in the config file.', file=sys.stderr)
        sys.exit(2)

directory_results = []

# open the database and search
with sqlite3.connect(os.path.join(config['archivebox_root'], 'data', 'index.sqlite3')) as conn:
    cursor = conn.cursor()
    results = cursor.execute(
        """
            SELECT DISTINCT pwd FROM core_snapshot INNER JOIN core_archiveresult ON core_archiveresult.snapshot_id = core_snapshot.id WHERE core_snapshot.title LIKE ? ORDER BY timestamp ASC
        """, [ f'%{sys.argv[1]}%' ])
    for row in results:
        directory_results += row

# no results
if len(directory_results) < 1:
    print(f'No results were found for the query "{sys.argv[1]}"', file=sys.stderr)
    sys.exit(0)

# loop through directories and begin the process
for directory in directory_results:

    # strip initial slash to make sure we get an absolute dir when we `os.path.join`
    if directory[0] == '/':
        directory = directory[1:]
    abs_directory = os.path.join(config['archivebox_root'], directory)

    filename_sanitised_search = sys.argv[1].replace(' ', '-')
    filename_sanitised_search = filename_sanitised_search.replace(':', '-')
    filename_sanitised_search = re.sub(r'[^a-zA-Z0-9-]', '-', filename_sanitised_search)

    # define the output epub file name
    today = datetime.strftime(datetime.now(), '%Y-%m-%d')
    output_path = os.path.join(config['output_dir'], f'{today}-{filename_sanitised_search}.epub')

    suffix = 0
    while os.path.exists(output_path):
        output_path = os.path.join(config['output_dir'], f'{today}-{filename_sanitised_search}_{suffix:05d}.epub')
        suffix += 1
    
    # pull in images using the node tool
    subprocess.run([
        config['invoke_node_cmdline'],
        config['embed_images_tool'],
        os.path.join(abs_directory, 'readability', 'content.html'),
        os.path.join(abs_directory, 'readability', 'content_images.html'),
        ], check=True)

    # convert to epub and dump to output dir
    subprocess.run([
        config['ebook_convert_cmdline'],
        os.path.join(abs_directory, 'readability', 'content_images.html'),
        output_path,
        '--epub-max-image-size',
        config['max_image_size'],
        '--output-profile',
        config['output_profile'],
        '--title',
        sys.argv[1]
    ], check=True)
