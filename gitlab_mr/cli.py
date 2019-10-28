import json
import os
from configparser import ConfigParser

import click
import gitlab

from gitlab_mr.merge_request import Actions, PrettyMergeRequest

APP_NAME = "Gitlab MR"


@click.group()
@click.pass_context
def cli(ctx):
    app_path = click.get_app_dir(APP_NAME, force_posix=True)
    if not os.path.exists(app_path):
        os.makedirs(app_path)

    config_path = os.path.join(app_path, "config.ini")

    ctx.obj = {"config_path": config_path}


@cli.command(short_help="Init cli util")
@click.option("--host", prompt=True)
@click.option("--token", prompt=True, hide_input=True)
@click.pass_obj
def init(obj, token, host):
    config = ConfigParser()

    config.add_section("gitlab")
    config.set("gitlab", "token", token)
    config.set("gitlab", "host", host)
    config.set("gitlab", "projects", "[]")

    config_path = obj["config_path"]
    with open(config_path, "w") as configfile:
        config.write(configfile)

    click.secho(
        f"Gitlab token has been successfully saved {click.format_filename(config_path)}"
    )


@cli.command(short_help="Auth user")
@click.pass_obj
@click.pass_context
def auth(ctx, obj):
    config = ConfigParser()

    if not os.path.exists(obj["config_path"]):
        raise click.ClickException("You need to init first")

    config.read(obj["config_path"])

    gl = gitlab.Gitlab(
        url=config.get("gitlab", "host"),
        private_token=config.get("gitlab", "token"),
        api_version="4",
        ssl_verify=True,
        timeout=10,
    )
    try:
        gl.auth()
    except gitlab.exceptions.GitlabAuthenticationError:
        raise click.ClickException(
            "Your token is invalid or expired\nRun edit and change token"
        )

    gl_user = gl.user
    projects = json.loads(config.get("gitlab", "projects"))

    obj.update(gl=gl, gl_user=gl_user, config=config, projects=projects)


@cli.command(short_help="Test that everything is ok")
@click.pass_obj
@click.pass_context
def test(ctx, obj):
    ctx.invoke(auth)
    if not obj["projects"]:
        click.secho("No projects are configured", err=True)
        return
    click.secho("Everything is OK")


@cli.command(short_help="Projects")
@click.option("-a", "--add", "action", flag_value="add", help="add project")
@click.option("-r", "--remove", "action", flag_value="remove", help="remove project")
@click.option(
    "-l", "--list", "action", flag_value="list", help="list projects", default=True
)
@click.argument("project", required=False)
@click.pass_obj
@click.pass_context
def projects(ctx, obj, action, project):
    ctx.invoke(auth)

    projects = obj["projects"]

    if action == "list":
        if not projects:
            click.secho("No projects configured")

        for project in projects:
            click.secho(f"\t{project}", fg="blue")
        return

    elif not project:
        raise click.UsageError("Project is required")

    elif action == "add":
        if project in projects:
            click.secho(f"Project '{project}' already exists", err=True)
            return
        projects.append(project)
        action_past_simple = "added"
    elif action == "remove":
        try:
            projects.remove(project)
        except ValueError:
            click.secho(f"Project '{project}' have never been there", err=True)
            return
        action_past_simple = "removed"

    config = obj["config"]
    with open(obj["config_path"], "w") as configfile:
        config.set("gitlab", "projects", json.dumps(projects))
        config.write(configfile)

    click.secho(f"Successfully {action_past_simple} '{project}' project")


@cli.command(short_help="Edit configuration file")
@click.pass_obj
def edit(obj):
    click.edit(filename=obj["config_path"])


@cli.command(short_help="View all active merge requests")
@click.pass_obj
@click.pass_context
def overview(ctx, obj):
    ctx.invoke(auth)
    projects = obj["projects"]
    if not projects:
        click.secho("No projects are configured")
        return

    gl = obj["gl"]

    for project in projects:
        g_project = gl.projects.get(project, lazy=True)
        mrs = g_project.mergerequests.list(state="opened")

        if mrs:
            click.secho(f"{project}:", fg="blue", bold=True)

        for mr in mrs:
            merge_request = PrettyMergeRequest(mr, obj["gl_user"])
            merge_request.pretty_overview()


@cli.command(short_help="Quick Actions")
@click.option("-c", "--count", "only_count", is_flag=True, help="return only count")
@click.pass_obj
@click.pass_context
def actions(ctx, obj, only_count):
    ctx.invoke(auth)
    projects = obj["projects"]
    if not projects and not only_count:
        click.secho("No projects are configured")
        return

    gl = obj["gl"]

    count = 0
    for project in projects:
        g_project = gl.projects.get(project, lazy=True)
        mrs = g_project.mergerequests.list(state="opened")

        for mr in mrs:
            merge_request = PrettyMergeRequest(mr, obj["gl_user"])
            if merge_request.action in Actions.notable_actions():
                count += 1
                if only_count:
                    continue

                click.secho(project, fg="blue", nl=False)
                click.secho(" | ", fg="bright_white", bold=True, nl=False)
                click.echo(merge_request.pretty_title, nl=False)
                click.secho(" | ", fg="bright_white", bold=True, nl=False)
                click.echo(merge_request.author, nl=False)
                click.secho(" | ", fg="bright_white", bold=True, nl=False)
                click.echo(merge_request.url, nl=False)
                click.secho(" | ", fg="bright_white", bold=True, nl=False)
                click.echo(merge_request.pretty_action, nl=False)
                click.echo()

    if only_count and count:
        click.echo(count)
