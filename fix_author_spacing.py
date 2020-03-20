import json
import glob
import os
files = sorted(glob.glob('project_info/*.json'))
ignore_set = {os.path.join('project_info', key)
              for key in ['aa_empty.json', 'zz_file_featured.json', 'zz_file_order.json']
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

