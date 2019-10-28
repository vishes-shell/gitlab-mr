import enum
from datetime import datetime, timezone
from typing import Tuple

import arrow
import click

AWARD_THUMBS_UP = "thumbsup"


class Actions(enum.Enum):
    ResolveDiscussions = "Resolve Discussions"
    ResolveConflicts = "Resolve Conflicts"
    ResolveOrDiscuss = "Resolve or Discuss"
    Merge = "MERGE"
    Review = "Do Review ASAP"

    WaitReview = "Wait for Review"
    WaitResolve = "Wait for Resolve"
    WaitOthers = "Wait for others"
    WaitFinish = "Wait for Resolve WIP"

    TellMerge = "Tell to Merge"

    @classmethod
    def notable_actions(cls):
        return (
            cls.ResolveDiscussions,
            cls.ResolveConflicts,
            cls.ResolveOrDiscuss,
            cls.Merge,
            cls.Review,
        )

    @classmethod
    def wait_actions(cls):
        return (cls.WaitFinish, cls.WaitOthers, cls.WaitResolve, cls.WaitReview)


class MergeRequest:
    def __init__(self, gitlab_obj, current_user):
        self.gitlab_obj = gitlab_obj
        self._current_user = current_user

    @staticmethod
    def _get_datetime_from_gitlab(dt_str):
        dt = datetime.strptime(dt_str[:19], "%Y-%m-%dT%H:%M:%S")
        return dt.replace(tzinfo=timezone.utc).astimezone(tz=None)

    def _is_me(self, id_=None):
        if id_ is None:
            id_ = self.gitlab_obj.author.get("id")
        return bool(self._current_user.id == id_)

    @property
    def url(self):
        return self.gitlab_obj.web_url

    @property
    def upvotes_count(self):
        return self.gitlab_obj.upvotes

    @property
    def description(self):
        return self.gitlab_obj.description

    @property
    def author(self):
        author = self.gitlab_obj.author.get("username")

        if self._is_me(self.gitlab_obj.author["id"]):
            author = f"You ({author})"

        return author

    @property
    def i_liked(self):
        if not hasattr(self, "_i_liked"):
            self.upvotes
        return getattr(self, "_i_liked")

    @property
    def upvotes(self) -> Tuple[str, datetime]:
        if not hasattr(self, "_upvotes"):
            upvotes = []
            self._i_liked = False
            for award in self.gitlab_obj.awardemojis.list():
                if award.name != AWARD_THUMBS_UP:
                    continue

                if self._is_me(award.user.get("id")):
                    username = "You"
                    self._i_liked = True
                else:
                    username = award.user.get("username")

                created_at = self._get_datetime_from_gitlab(award.created_at[:-1])

                upvotes.append((username, created_at))

            self._upvotes = upvotes

        return self._upvotes

    @property
    def created_at(self):
        return self._get_datetime_from_gitlab(self.gitlab_obj.created_at)

    @property
    def discussion_data(self):
        discussions = self.gitlab_obj.discussions.list()
        data = {"raw": discussions, "resolved": [], "new": [], "wait": []}
        for dis in discussions:
            notable = False
            me_involved = False
            for note in dis.attributes["notes"]:
                if not note["resolvable"]:
                    break

                if note["resolved"]:
                    data["resolved"].append(dis)
                    break

                if self._is_me(note["author"]["id"]):
                    notable = False
                    me_involved = True
                else:
                    notable = True
            else:
                if notable and me_involved:
                    data["new"].append(dis)
                else:
                    data["wait"].append(dis)
        return data

    @property
    def action(self):
        discussion_data = self.discussion_data
        if self.gitlab_obj.work_in_progress:
            return Actions.WaitFinish
        if self._is_me():
            if discussion_data["new"]:
                return Actions.ResolveDiscussions
            elif discussion_data["wait"]:
                return Actions.WaitResolve

            if self.upvotes_count < 2:
                return Actions.WaitReview
            else:
                return Actions.Merge
        else:
            if discussion_data["new"]:
                return Actions.ResolveOrDiscuss
            elif discussion_data["wait"]:
                return Actions.WaitResolve

            if not self.i_liked:
                return Actions.Review
            elif self.upvotes_count >= 2:
                return Actions.TellMerge
            else:
                return Actions.WaitOthers


class PrettyMergeRequest(MergeRequest):
    @property
    def pretty_title(self):
        style_kwargs = {"bold": True}
        if self.gitlab_obj.work_in_progress:
            style_kwargs.update(fg="cyan", dim=True)
        elif self._is_me():
            style_kwargs.update(fg="green", dim=True)
        else:
            style_kwargs.update(fg="bright_green")

        return click.style(self.gitlab_obj.title, **style_kwargs)

    @property
    def pretty_likes(self):
        likes = str(self.upvotes_count)
        likes_expanded = ", ".join(
            f"{username}({arrow.get(created_at).humanize()})"
            for username, created_at in self.upvotes
        )

        if self.upvotes_count:
            likes = f"{likes} [{likes_expanded}]"
        return likes

    @property
    def pretty_created_at(self):
        created_at = self.created_at
        style_kwargs = {}
        if (datetime.utcnow().astimezone(tz=None) - created_at).days >= 3:
            style_kwargs.update(blink=True, fg="red")
        age = arrow.get(created_at).humanize()
        return click.style(f"{created_at:%d.%m %H:%M} ({age})", **style_kwargs)

    @property
    def pretty_action(self):
        action = self.action

        style_kwargs = {}
        if action in Actions.notable_actions():
            style_kwargs.update(blink=True, fg="bright_red")
        elif action in Actions.wait_actions():
            style_kwargs.update(fg="green")
        else:
            style_kwargs.update(fg="cyan")

        return click.style(action.value, **style_kwargs)

    def pretty_overview(self) -> None:
        click.echo("\t", nl=False)
        click.echo(self.pretty_title)

        for attr in ("url", "description", "likes", "author", "created_at", "action"):
            pretty_attr = attr.replace("_", " ").capitalize()
            click.secho(f"\t\t{pretty_attr}: ", nl=False, bold=True)

            try:
                value = getattr(self, f"pretty_{attr}")
            except AttributeError:
                value = getattr(self, attr)
            click.echo(value)

        click.echo()
