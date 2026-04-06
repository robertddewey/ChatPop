"""
Collapse AnonymousIdentityLink into ChatParticipation.

This migration introduces ``ChatParticipation.is_anonymous_identity`` and
migrates every existing ``AnonymousIdentityLink`` row to set the
``user`` and ``is_anonymous_identity`` fields directly on the linked
``ChatParticipation``. The ``AnonymousIdentityLink`` model is then
removed entirely.

Per project policy, migrations are normally schema-only — this migration
intentionally uses ``RunPython`` because the data move from a separate
link table into a flag/FK on the participation row is the entire point
of the change and cannot be expressed declaratively.
"""

from django.conf import settings
from django.db import migrations, models, transaction


def forwards_collapse_links(apps, schema_editor):
    AnonymousIdentityLink = apps.get_model("chats", "AnonymousIdentityLink")
    ChatParticipation = apps.get_model("chats", "ChatParticipation")

    count = 0
    with transaction.atomic():
        for link in AnonymousIdentityLink.objects.select_related("participation").all():
            participation = link.participation
            if participation is None:
                continue
            participation.user_id = link.user_id
            participation.is_anonymous_identity = True
            participation.save(update_fields=["user", "is_anonymous_identity"])
            count += 1
    print(f"  collapsed {count} AnonymousIdentityLink row(s) into ChatParticipation")


def reverse_collapse_links(apps, schema_editor):
    AnonymousIdentityLink = apps.get_model("chats", "AnonymousIdentityLink")
    ChatParticipation = apps.get_model("chats", "ChatParticipation")

    count = 0
    for participation in ChatParticipation.objects.filter(is_anonymous_identity=True):
        if participation.user_id is None:
            continue
        AnonymousIdentityLink.objects.get_or_create(
            user_id=participation.user_id,
            chat_room_id=participation.chat_room_id,
            participation=participation,
        )
        participation.user_id = None
        participation.is_anonymous_identity = False
        participation.save(update_fields=["user", "is_anonymous_identity"])
        count += 1
    print(f"  re-extracted {count} anonymous identity link row(s)")


class Migration(migrations.Migration):

    # Postgres will not create a unique index in the same transaction that has
    # pending trigger events from prior DDL/DML in the same migration. Run each
    # operation in its own transaction.
    atomic = False

    dependencies = [
        ("chats", "0011_remove_anonymousidentitylink_unique_user_chat_anonymous_link_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Add the new flag (default False) so the data migration can populate it.
        migrations.AddField(
            model_name="chatparticipation",
            name="is_anonymous_identity",
            field=models.BooleanField(
                default=False,
                db_index=True,
                help_text=(
                    "True if this participation is a registered user's claimed "
                    "anonymous identity (user is set but username is not their "
                    "reserved_username)"
                ),
            ),
        ),
        # 2. Drop the old uniqueness constraint FIRST — otherwise the data move
        #    below fails for users who already have both a registered participation
        #    and a linked anonymous participation in the same chat (the new one
        #    would violate the old "one participation per (chat, user)" rule).
        migrations.RemoveConstraint(
            model_name="chatparticipation",
            name="unique_chat_user",
        ),
        # 3. Move the data from AnonymousIdentityLink onto ChatParticipation.
        migrations.RunPython(forwards_collapse_links, reverse_collapse_links),
        # 4. Add the new constraints that allow 1 registered + N anonymous per (chat, user).
        migrations.AddConstraint(
            model_name="chatparticipation",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("is_anonymous_identity", False),
                    ("user__isnull", False),
                ),
                fields=("chat_room", "user"),
                name="unique_chat_user_registered",
            ),
        ),
        migrations.AddConstraint(
            model_name="chatparticipation",
            constraint=models.UniqueConstraint(
                condition=models.Q(("user__isnull", False)),
                fields=("chat_room", "user", "username"),
                name="unique_chat_user_username",
            ),
        ),
        # 5. Drop the (now empty) AnonymousIdentityLink table entirely.
        migrations.DeleteModel(
            name="AnonymousIdentityLink",
        ),
    ]
