import json
import glob
import os
for base_path in ['papers_info', 'others_info']:
    files = sorted(glob.glob(os.path.join(base_path, '*.json')))
    ignore_set = {os.path.join(base_path, key)
                  for key in ['aa_empty.json', 'zz_file_order.json',]
                  }
    for fi in files:
        if fi in ignore_set:
            continue
        data = json.load(open(fi))
        authors = data['authors']
        authors = authors.split(', ')
        authors = [author.strip().replace(' ', '&nbsp;') for author in authors]
        authors = ', '.join(authors)
        data['authors'] = authors
        with open(fi, 'w') as of:
            json.dump(data, of, indent=2)

