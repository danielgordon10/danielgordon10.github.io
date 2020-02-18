#!/bin/bash

python make_templates_index.py
python remove_pingendo.py
chmod -R +r *
chmod 700 old
chmod 700 cv.docx
#scp -r * xkcd@tricycle.cs.washington.edu:/cse/web/homes/xkcd/
rsync -avW * xkcd@bicycle.cs.washington.edu:/cse/web/homes/xkcd --exclude *.swp
#git add -A
#git commit -m "update"
#git push github master


