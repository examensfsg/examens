#!/bin/bash
set -e

# we want to avoid tracking exam PDFs in git
# in order to do this, exams are kept in a separate branch from the rest,
# which contains a single commit that gets continuously amended.
# the database branch is used to publish to github pages.

# we don't want to keep exam history because:
# - exams takes a lot of space and github has limited storage space
# - eventual copyright takedown requests must be fulfilled,
#     and history would have to be cleared (although nothing can be done for forks...)

# also: git LFS doesn't work with github pages, but that doesn't matter
# since there's normally no history stored for the PDFs.

git switch database
git merge master --squash -X theirs   # note that deleted files on master will still be present!
# --> dbhelper/main.py add ...
git add exam/ db/

git commit -m "database update"
# if commit is amended, github will not diff objects correctly and the whole thing is reuploaded!
# so only change history once in a while, squashing commits.
git rebase -i master -X theirs

# --> git push -f
git switch master
