# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chats", "0016_add_light_mode_theme"),
    ]

    operations = [
        migrations.AddField(
            model_name='chattheme',
            name='messages_area_container',
            field=models.TextField(
                default='bg-white',
                help_text="Background classes for messages area container (parent of pattern layer)"
            ),
        ),
    ]
