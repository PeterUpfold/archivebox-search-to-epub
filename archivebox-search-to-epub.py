#!/usr/bin/env python3
#
# archivebox-search-to-epub
#
# Uses `ebook-convert` to convert Readability version of an ArchiveBox item for consuming
# articles offline in ePub format.
#

import json
import subprocess
import sys
import sqlite3
import re
import os
from datetime import datetime
from shutil import copyfile
from subprocess import CalledProcessError
import logging
import tempfile

def query_database(config, query, args = None):
    """Query the SQLite database
    """
    with sqlite3.connect(os.path.join(config['archivebox_root'], 'data', 'index.sqlite3')) as conn:
        cursor = conn.cursor()
        cursor.row_factory = sqlite3.Row
        if args is not None:
            results = cursor.execute(query, args)
        else:
            results = cursor.execute(query)
    
    return [dict(row) for row in results.fetchall()]    

logname = os.path.join(tempfile.gettempdir(), os.path.basename(__file__) + '.log')
logging.basicConfig(level=logging.ERROR, filename=logname)

with open(os.path.join(os.path.dirname(__file__), 'volatile/config.json'), 'r') as json_file:
    config = json.load(json_file)

# must provide the search query as the first argument
if len(sys.argv) < 2:
    print('Please provide the search query as the first argument, or use -t for today''s articles.', file=sys.stderr)
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

results = []

article_title = sys.argv[1]

# open the database and search
if sys.argv[1] != '-t':
    logging.info(f'Will query for article title {article_title}')
    results = query_database(config, """
                SELECT DISTINCT pwd, title FROM core_snapshot INNER JOIN core_archiveresult ON core_archiveresult.snapshot_id = core_snapshot.id WHERE core_snapshot.title LIKE ? ORDER BY timestamp ASC
            """, [ f'%{article_title}%' ])

else: # today's results
    logging.info(f'Will query for articles -1 day')
    results = query_database(config, """
                SELECT DISTINCT pwd, title FROM core_snapshot INNER JOIN core_archiveresult ON core_archiveresult.snapshot_id = core_snapshot.id WHERE core_snapshot.added > DATE('now','-1 day') ORDER BY timestamp ASC
            """)
# no results
if len(results) < 1:
    print(f'No results were found for the query "{article_title}"', file=sys.stderr)
    sys.exit(0)

logging.info(f'Found {len(results)} results')

# loop through directories and begin the process
for item in results:

    logging.info(f'Processing {item["pwd"]} with title {item["title"]}')
    if item['title'] is None:
        logging.error(f'Cannot operate on an archive result with no title -- {item["pwd"]}')
        continue

    # strip initial slash to make sure we get an absolute dir when we `os.path.join`
    if item['pwd'][0] == '/':
        item['pwd'] = item['pwd'][1:]
    abs_directory = os.path.join(config['archivebox_root'], item['pwd'])

    filename_sanitised_search = item['title'].replace(' ', '-')
    filename_sanitised_search = filename_sanitised_search.replace(':', '-')
    filename_sanitised_search = re.sub(r'[^a-zA-Z0-9-]', '-', filename_sanitised_search)

    logging.info(f'{item["title"]} has sanitised name {filename_sanitised_search}')

    # define the output epub file name
    today = datetime.strftime(datetime.now(), '%Y-%m-%d')
    output_path = os.path.join(config['output_dir'], f'{today}-{filename_sanitised_search}.epub')

    suffix = 0
    while os.path.exists(output_path):
        output_path = os.path.join(config['output_dir'], f'{today}-{filename_sanitised_search}_{suffix:05d}.epub')
        suffix += 1
    
    logging.info(f'Output filename {output_path}')

    if not os.path.exists(os.path.join(abs_directory, 'readability', 'content.html')):
        logging.error(f"{item['pwd']}: Readability file {os.path.join(abs_directory, 'readability', 'content.html')} does not exist.")
        continue

    # pull in images using the node tool
    try:
        logging.info(f"Will invoke {config['invoke_node_cmdline']} {config['embed_images_tool']} {os.path.join(abs_directory, 'readability', 'content.html')} {os.path.join(abs_directory, 'readability', 'content_images.html')}")
        subprocess.run([
            config['invoke_node_cmdline'],
            config['embed_images_tool'],
            os.path.join(abs_directory, 'readability', 'content.html'),
            os.path.join(abs_directory, 'readability', 'content_images.html'),
            ], check=True)
    except CalledProcessError:
        logging.error(f'Failed to extract images from web for {filename_sanitised_search}. Will skip images')
        copyfile(os.path.join(abs_directory, 'readability', 'content.html'), os.path.join(abs_directory, 'readability', 'content_images.html'))

    # convert to epub and dump to output dir
    try:
        logging.info(f"Will invoke {config['ebook_convert_cmdline']} {os.path.join(abs_directory, 'readability', 'content_images.html')} {output_path} '--epub-max-image-size' {config['max_image_size']} '--output-profile' {config['output_profile']} --title {item['title']} ")
        subprocess.run([
            config['ebook_convert_cmdline'],
            os.path.join(abs_directory, 'readability', 'content_images.html'),
            output_path,
            '--epub-max-image-size',
            config['max_image_size'],
            '--output-profile',
            config['output_profile'],
            '--title',
            item['title']
        ], check=True)
    except CalledProcessError:
        logging.error(f'Failed to convert {filename_sanitised_search}')

print(f'Complete. Check log at {logname}')