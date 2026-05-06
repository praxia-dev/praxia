"""Per-feature CLI subcommand modules.

Each module exposes a Typer app named `<feature>_app` that `cli/main.py`
mounts via `app.add_typer(<feature>_app, name="<feature>")`. Top-level
commands (init / run / list / consolidate / freeze / ui / serve / export)
remain in `cli/main.py`.

Split by:
    - user.py        — praxia user {create,list,grant,update,delete,...}
    - skill.py       — praxia skill {run,promote,distribute}
    - prompt.py      — praxia prompt {create,list,distribute,delete}
    - connector.py   — praxia connector {list,pull,push}
    - policy.py      — praxia policy {add,list,remove,test}
    - admin.py       — praxia admin {export-*, memory-policy-*}
    - memory.py      — praxia memory {mode,backend,show}
    - oauth.py       — praxia oauth {start,callback,list,revoke}
    - config.py      — praxia config {show,get,set,init,path}
    - experiment.py  — praxia experiment {create,list,start,...,results}
    - webhook.py     — praxia webhook {add,list,remove,test}
    - mcp.py         — praxia mcp {serve,tools}
"""
