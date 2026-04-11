from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('chats', '0015_chatroom_host_pinned_message'),
    ]

    operations = [
        migrations.RenameField(
            model_name='message',
            old_name='is_broadcast',
            new_name='is_highlight',
        ),
        migrations.RenameField(
            model_name='chattheme',
            old_name='broadcast_icon_color',
            new_name='highlight_icon_color',
        ),
        migrations.RemoveField(
            model_name='chatroom',
            name='host_pinned_message',
        ),
    ]
