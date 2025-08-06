#!/bin/bash

python make_project_info_index.py
python update_footer.py
python fix_author_spacing.py
chmod -R +r *
chmod 700 cv.docx
# rsync -avW --info=progress2 * xkcd@bicycle.cs.washington.edu:/cse/web/homes/xkcd --exclude *.swp --exclude .git
git add -A
git commit -m "update `date`"
git push origin master
