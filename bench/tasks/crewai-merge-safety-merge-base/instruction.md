# check_merge_safety reports false deletions for branches forked from an older master

`scripts/check_merge_safety.py <branch>` is meant to catch branches that would delete files still
tracked in master. Today, if master gained new files after the branch was forked, every one of those
files is reported as "deleted" and the script exits 1, although the branch never touched them.

Only what the branch itself changed since it forked from master (its merge-base) may be considered.
The tests check the exact git command the script runs, which must be
`git diff --name-status <master>...<branch>`. Update the module docstring, the function docstring and
the CLI description so they describe the new behaviour.
