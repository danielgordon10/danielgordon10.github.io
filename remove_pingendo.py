import glob
import os
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
        if not ('<pingendo' in line or
                '</pingendo>' in line or
                'Pingendo_logo' in line):
            new_lines.append(line)
    new_file = open(file, 'w')
    new_file.write(''.join(new_lines))
    new_file.close()
        
