import glob
import json
import pdb
import os
for base_path in ['papers', 'other']:
    files = sorted(glob.glob(os.path.join(base_path, 'info', '*.json')))[1:-1]  # leave off the fake ones
    data = [(fi, json.load(open(fi, 'r'))) for fi in files]
    data = sorted(data, key=lambda x: x[1]['date'], reverse=True)
    file_names_in_order = [os.path.basename(dd[0]) for dd in data]
    json.dump(file_names_in_order, open(os.path.join(base_path, 'info', 'zz_file_order.json'), 'w'), indent=2)
    print('Created', base_path, 'index')
