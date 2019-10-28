try:
    from gitlab_mr import cli
except ImportError:
    from . import cli

cli.cli()
