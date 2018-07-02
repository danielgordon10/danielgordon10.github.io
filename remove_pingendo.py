import glob
import os
from datetime import datetime
folders = [ff for ff in glob.glob('*') if os.path.isdir(ff)]
files = glob.glob('*.html')
while len(folders) > 0:
    folder = folders.pop()
    new_folders = [ff for ff in glob.glob(os.path.join(folder, '*')) if os.path.isdir(ff)]
    folders.extend(new_folders)
    new_files = glob.glob(os.path.join(folder, '*.html'))
    files.extend(new_files)
for file in files:
    lines = [line for line in open(file)]
    new_lines = []
    for line in lines:
        if ('<pingendo' in line or
                '</pingendo>' in line or
                'Pingendo_logo' in line):
            continue
        elif 'Last Updated' in line:
            import pdb
            #pdb.set_trace()
            start_padding = line[:len(line) - len(line.lstrip())]
            line = start_padding + '<p>&copy; 2018 Daniel Gordon. Last Updated ' + datetime.now().strftime('%B') + ' ' + str(datetime.now().year) + '.</p>\n'
        elif line == '        </div>    </div>':
            line = '         </div>\n    </div>'

        new_lines.append(line)

    new_file = open(file, 'w')
    new_file.write(''.join(new_lines))
    new_file.close()
    print('Updated', file)
        
