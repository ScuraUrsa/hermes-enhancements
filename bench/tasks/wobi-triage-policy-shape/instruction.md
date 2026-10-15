# load_policy crashes on a YAML policy file with the wrong shape

`crewai/llm_triage/policy.py` `load_policy(path)` is supposed to fall back to the default policy when
the policy file is unreadable or invalid. A file that is valid YAML but has the wrong shape, for example
a top-level list:

```yaml
- item1
- item2
```

crashes with `AttributeError` instead. It must fall back to the defaults (a `TriagePolicy` with the
default rules) like any other invalid config.
