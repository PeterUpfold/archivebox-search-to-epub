#!/usr/bin/env python3
#

import sys
import json
import tempfile
import subprocess
import os

with open(os.path.join(os.path.dirname(__file__), 'volatile/config.json'), 'r') as json_file:
    config = json.load(json_file)

# must provide the input file as the first argument
if len(sys.argv) < 2:
    print('Please provide the input file as the first argument.', file=sys.stderr)
    sys.exit(1)


def extract_urls_from_json(json_file_path):
    with open(json_file_path) as file:
        data = json.load(file)
    
    urls = []
    find_urls(data, urls)
    return urls

def find_urls(data, urls):
    if isinstance(data, dict):
        for key, value in data.items():
            if key == 'url':
                urls.append(value)
            elif isinstance(value, (dict, list)):
                find_urls(value, urls)
    elif isinstance(data, list):
        for item in data:
            find_urls(item, urls)

url_text = ''

for url in extract_urls_from_json(sys.argv[1]):
        print(url)
        url_text += url + '\n'


#result = subprocess.run(config['archivebox_add_args'], input=url_text, text=True, capture_output=True)

#print(result.returncode)