# danielgordon10.github.io
Personal website
https://danielgordon10.github.io/index.html

## Instructions on adding a new page:
1. Copy [project_info/aa_empty.json](project_info/aa_empty.json) to new file.
1. Fill in the missing values.
1. Copy[projects/aa_template.html](rojects/aa_template.html) to new file.
1. Do any in place HTML edits there.
1. If you want it to appear on the featured section, it must be added manually to [project_info/zz_file_featured.json](project_info/zz_file_featured.json).
1. If you need to add an image (because there's no video), add it to [images/projects](images/projects).
1. When done call `sh export_website.sh` which does a bit of post-processing, and pushes the files to the server.

## Instructions on adding an image to info.html
1. Put the image in [images/info_images](images/info_images).
1. Make sure the image is 1920 x 1440.
1. Add it to [info.html](info.html), using `active` class if it should be the first one.
1. Add an indicator thing by copying the `li`.

## How it works:
- JSON files/values are loaded using javascript calls. 
- The code to call and process the JSON for each main page is in [assets/js/project_template.js](assets/js/project_template.js).
- The code to call and process the JSON for the global projects page is in [assets/js/project_page.js](assets/js/project_page.js).
