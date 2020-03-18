#!/bin/bash

python make_project_info_index.py
python remove_pingendo.py
python fix_author_spacing.py
chmod -R +r *
chmod 700 cv.docx
#scp -r * xkcd@tricycle.cs.washington.edu:/cse/web/homes/xkcd/
rsync -avW --info=progress2 * xkcd@bicycle.cs.washington.edu:/cse/web/homes/xkcd --exclude *.swp
#git add -A
#git commit -m "update"
#git push github master


